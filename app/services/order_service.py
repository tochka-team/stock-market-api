import logging
import uuid
from typing import List, Optional, Union

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.orders import orders_table
from app.schemas.order import (
    Direction,
    LimitOrderBody,
    MarketOrderBody,
    OrderBase,
    OrderStatus,
)
from app.schemas.user import User
from app.services.balance_service import BalanceService
from app.services.matching_engine import MatchingEngine

logger = logging.getLogger(__name__)


class OrderService:
    def __init__(self, db: AsyncConnection):
        self.db = db
        self.balance_service = BalanceService(db)
        self.matching_engine = MatchingEngine(db)

    async def _map_row_to_order_base(
        self, order_row: Optional[dict]
    ) -> Optional[OrderBase]:
        """Вспомогательный метод для маппинга строки из БД в OrderBase с учетом alias."""
        if not order_row:
            return None

        order_dict = dict(order_row)

        if "filled_qty" in order_dict and "filled" not in order_dict:
            pass

        return OrderBase.model_validate(order_dict)

    async def _get_order_from_db_by_id(
        self, order_id: uuid.UUID
    ) -> Optional[OrderBase]:
        """Загружает ордер из БД и мапит его в OrderBase."""
        stmt = select(orders_table).where(orders_table.c.id == order_id)
        result = await self.db.execute(stmt)
        order_row = result.mappings().one_or_none()
        return await self._map_row_to_order_base(order_row)

    async def create_order(
        self, current_user: User, order_data: Union[MarketOrderBody, LimitOrderBody]
    ) -> OrderBase:
        order_id_obj = uuid.uuid4()
        user_id_obj = current_user.id
        price_value = None
        is_limit_order = isinstance(order_data, LimitOrderBody)

        if is_limit_order:
            price_value = order_data.price
            if price_value <= 0:
                raise ValueError("Price for limit order must be positive.")

        if order_data.qty <= 0:
            raise ValueError("Order quantity must be positive.")

        ticker_to_block_or_check = ""
        amount_to_block_or_check = 0

        if order_data.direction == Direction.BUY:
            ticker_to_block_or_check = "RUB"
            if not is_limit_order:
                logger.warning(
                    f"Market BUY order for user {user_id_obj} - balance blocking not implemented based on estimated price yet."
                )

            elif price_value:
                amount_to_block_or_check = price_value * order_data.qty

        elif order_data.direction == Direction.SELL:
            ticker_to_block_or_check = order_data.ticker
            amount_to_block_or_check = order_data.qty

        if (
            not ticker_to_block_or_check
            or (
                is_limit_order
                and order_data.direction == Direction.BUY
                and amount_to_block_or_check <= 0
            )
            or (
                order_data.direction == Direction.SELL and amount_to_block_or_check <= 0
            )
        ):
            if not (
                order_data.direction == Direction.BUY
                and not is_limit_order
                and amount_to_block_or_check == 0
            ):
                raise ValueError(
                    "Invalid order parameters for balance check or zero amount to block."
                )

        if amount_to_block_or_check > 0:
            blocked_successfully = await self.balance_service.block_funds(
                user_id=user_id_obj,
                ticker=ticker_to_block_or_check,
                amount_to_block=amount_to_block_or_check,
            )
            if not blocked_successfully:
                raise ValueError(
                    f"Insufficient balance of {ticker_to_block_or_check} to place order."
                )
        else:
            logger.info(
                f"No funds to block for order type {order_data.direction} (likely market BUY without price estimation)."
            )

        insert_stmt = (
            insert(orders_table)
            .values(
                id=order_id_obj,
                user_id=user_id_obj,
                ticker=order_data.ticker,
                direction=order_data.direction,
                qty=order_data.qty,
                price=price_value,
                status=OrderStatus.NEW,
                filled_qty=0,
            )
            .returning(orders_table.c.id)
        )

        try:
            result = await self.db.execute(insert_stmt)
            created_order_id = result.scalar_one()

            if not created_order_id:
                logger.error(
                    f"Order creation failed for user {user_id_obj} after funds were blocked, no ID returned."
                )
                raise Exception(
                    "Order creation post-block failed unexpectedly (no ID)."
                )

            await self.matching_engine.process_new_order(created_order_id)
            logger.info(f"Matching engine processed order {created_order_id}")

            final_order_state = await self._get_order_from_db_by_id(created_order_id)
            if not final_order_state:
                logger.error(
                    f"Order {created_order_id} not found after matching attempt. This should not happen."
                )
                raise Exception(
                    f"Order {created_order_id} disappeared after matching attempt."
                )

            return final_order_state

        except Exception as e:
            logger.error(
                f"Error in create_order service for user {user_id_obj}: {e}",
                exc_info=True,
            )
            raise

    async def get_order_by_id_for_user(
        self, order_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[OrderBase]:
        stmt = select(orders_table).where(
            (orders_table.c.id == order_id) & (orders_table.c.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        order_row = result.mappings().one_or_none()
        return await self._map_row_to_order_base(order_row)

    async def get_orders_by_user(
        self, user_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[OrderBase]:
        stmt = (
            select(orders_table)
            .where(orders_table.c.user_id == user_id)
            .order_by(orders_table.c.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        order_rows = result.mappings().all()

        orders_list = [
            mapped_order
            for row in order_rows
            if (mapped_order := await self._map_row_to_order_base(row)) is not None
        ]
        return orders_list

    async def cancel_order(self, order_id: uuid.UUID, current_user: User) -> bool:
        user_id = current_user.id
        logger.debug(f"Attempting to cancel order {order_id} for user {user_id}")

        get_order_stmt = select(orders_table).where(orders_table.c.id == order_id)
        order_res = await self.db.execute(get_order_stmt)
        order_to_cancel_row = order_res.mappings().one_or_none()

        if not order_to_cancel_row:
            raise ValueError(f"Order with ID '{order_id}' not found.")

        if order_to_cancel_row["user_id"] != user_id:
            raise PermissionError("User not authorized to cancel this order.")

        current_status = order_to_cancel_row["status"]
        if current_status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]:
            raise ValueError(
                f"Order cannot be cancelled. Current status: {current_status}."
            )

        unblocked_successfully = True
        remaining_qty_to_unblock = (
            order_to_cancel_row["qty"] - order_to_cancel_row["filled_qty"]
        )

        if remaining_qty_to_unblock > 0:
            amount_to_unblock = 0
            ticker_to_unblock = ""

            if order_to_cancel_row["direction"] == Direction.BUY:
                ticker_to_unblock = "RUB"
                if order_to_cancel_row["price"] is not None:
                    amount_to_unblock = (
                        order_to_cancel_row["price"] * remaining_qty_to_unblock
                    )
                else:
                    logger.warning(
                        f"Market BUY order {order_id}: Cannot determine amount to unblock without original locked amount or price."
                    )

            elif order_to_cancel_row["direction"] == Direction.SELL:
                ticker_to_unblock = order_to_cancel_row["ticker"]
                amount_to_unblock = remaining_qty_to_unblock

            if ticker_to_unblock and amount_to_unblock > 0:
                unblocked_successfully = await self.balance_service.unblock_funds(
                    user_id=user_id,
                    ticker=ticker_to_unblock,
                    amount_to_unblock=amount_to_unblock,
                )
                if not unblocked_successfully:
                    raise Exception(
                        f"Critical error: Failed to unblock funds for order {order_id}. Cancellation aborted."
                    )

        if unblocked_successfully:
            update_stmt = (
                update(orders_table)
                .where(orders_table.c.id == order_id)
                .values(
                    status=OrderStatus.CANCELLED,
                )
                .returning(orders_table.c.id)
            )

            result = await self.db.execute(update_stmt)
            updated_id = result.scalar_one_or_none()

            if updated_id:
                logger.info(
                    f"Order {order_id} successfully cancelled and funds (if any) unblocked by user {user_id}."
                )
                return True
            else:
                raise Exception("Failed to update order status after unblocking funds.")
        else:
            raise Exception("Fund unblocking failed, order cancellation aborted.")
