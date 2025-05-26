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

logger = logging.getLogger(__name__)


class OrderService:
    def __init__(self, db: AsyncConnection):
        self.db = db
        self.balance_service = BalanceService(db)

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
                raise NotImplementedError(
                    "Balance check for market BUY orders is not yet fully implemented without price estimation."
                )
            amount_to_block_or_check = price_value * order_data.qty

        elif order_data.direction == Direction.SELL:
            ticker_to_block_or_check = order_data.ticker
            amount_to_block_or_check = order_data.qty

        if not ticker_to_block_or_check or amount_to_block_or_check <= 0:
            raise ValueError("Invalid order parameters for balance check.")

        blocked_successfully = await self.balance_service.block_funds(
            user_id=user_id_obj,
            ticker=ticker_to_block_or_check,
            amount_to_block=amount_to_block_or_check,
        )

        if not blocked_successfully:
            raise ValueError(
                f"Insufficient balance of {ticker_to_block_or_check} to place order."
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
            .returning(
                orders_table.c.id,
                orders_table.c.user_id,
                orders_table.c.ticker,
                orders_table.c.direction,
                orders_table.c.qty,
                orders_table.c.price,
                orders_table.c.status,
                orders_table.c.filled_qty,
                orders_table.c.timestamp,
                orders_table.c.updated_at,
            )
        )

        try:
            result = await self.db.execute(insert_stmt)
            created_order_row = result.mappings().one_or_none()

            if not created_order_row:
                logger.error(
                    f"Order creation failed for user {user_id_obj} after funds were (supposedly) blocked."
                )
                raise Exception("Order creation post-block failed unexpectedly.")

            order_dict = dict(created_order_row)
            if "filled_qty" in order_dict and "filled" not in order_dict:
                order_dict["filled"] = order_dict.pop("filled_qty")
            return OrderBase.model_validate(order_dict)

        except Exception as e:
            logger.error(
                f"Error creating order for user {user_id_obj} (service level): {e}",
                exc_info=True,
            )
            raise

    async def get_order_by_id_for_user(
        self, order_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[OrderBase]:
        """
        Получает ордер по ID, проверяя, что он принадлежит указанному пользователю.
        """
        stmt = select(orders_table).where(
            (orders_table.c.id == order_id) & (orders_table.c.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        order_row = result.mappings().one_or_none()

        if order_row:
            order_dict = dict(order_row)
            if "filled_qty" in order_dict and "filled" not in order_dict:
                order_dict["filled"] = order_dict.pop("filled_qty")
            return OrderBase.model_validate(order_dict)
        return None

    async def get_orders_by_user(
        self, user_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[OrderBase]:
        """
        Получает список всех ордеров (пока без фильтра по активным) для указанного пользователя.
        """
        stmt = (
            select(orders_table)
            .where(orders_table.c.user_id == user_id)
            .order_by(orders_table.c.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        order_rows = result.mappings().all()

        orders_list = []
        for row in order_rows:
            order_dict = dict(row)
            if "filled_qty" in order_dict and "filled" not in order_dict:
                order_dict["filled"] = order_dict.pop("filled_qty")
            orders_list.append(OrderBase.model_validate(order_dict))
        return orders_list

    async def cancel_order(self, order_id: uuid.UUID, current_user: User) -> bool:
        user_id = current_user.id
        logger.debug(f"Attempting to cancel order {order_id} for user {user_id}")

        get_order_stmt = select(
            orders_table.c.id,
            orders_table.c.user_id,
            orders_table.c.status,
            orders_table.c.ticker,
            orders_table.c.direction,
            orders_table.c.qty,
            orders_table.c.filled_qty,
            orders_table.c.price,
        ).where(orders_table.c.id == order_id)

        order_res = await self.db.execute(get_order_stmt)
        order_to_cancel_map = order_res.mappings().one_or_none()

        if not order_to_cancel_map:
            raise ValueError(f"Order with ID '{order_id}' not found.")

        if order_to_cancel_map["user_id"] != user_id:
            raise PermissionError("User not authorized to cancel this order.")

        current_status = order_to_cancel_map["status"]
        if current_status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]:
            raise ValueError(
                f"Order cannot be cancelled. Current status: {current_status}."
            )

        unblocked_successfully = False
        if (
            current_status == OrderStatus.NEW
            or current_status == OrderStatus.PARTIALLY_EXECUTED
        ):
            amount_to_unblock = 0
            ticker_to_unblock = ""

            remaining_qty_to_unblock = (
                order_to_cancel_map["qty"] - order_to_cancel_map["filled_qty"]
            )

            if remaining_qty_to_unblock > 0:
                if order_to_cancel_map["direction"] == Direction.BUY:
                    ticker_to_unblock = "RUB"
                    if order_to_cancel_map["price"] is None:
                        logger.warning(
                            f"Cannot determine amount to unblock for market BUY order {order_id} without price."
                        )
                    else:
                        amount_to_unblock = (
                            order_to_cancel_map["price"] * remaining_qty_to_unblock
                        )

                elif order_to_cancel_map["direction"] == Direction.SELL:
                    ticker_to_unblock = order_to_cancel_map["ticker"]
                    amount_to_unblock = remaining_qty_to_unblock

                if ticker_to_unblock and amount_to_unblock > 0:
                    unblocked_successfully = await self.balance_service.unblock_funds(
                        user_id=user_id,
                        ticker=ticker_to_unblock,
                        amount_to_unblock=amount_to_unblock,
                    )
                    if not unblocked_successfully:
                        raise Exception(
                            f"Failed to unblock funds for order {order_id}, cancelling operation."
                        )
                else:
                    unblocked_successfully = True
            else:
                unblocked_successfully = True

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
                logger.error(
                    f"Failed to update status for order {order_id} after funds unblocked."
                )
                raise Exception("Failed to update order status after unblocking funds.")
        else:
            logger.error(
                f"Fund unblocking failed for order {order_id}, cancellation aborted."
            )
            raise Exception("Fund unblocking failed, order cancellation aborted.")
