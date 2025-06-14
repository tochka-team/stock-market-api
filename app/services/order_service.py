import logging
import uuid
from typing import List, Optional, Union
from datetime import datetime, timezone

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.instruments import instruments_table
from app.db.models.orders import orders_table
from app.schemas.order import (
    AnyOrderResponse,
    CreateOrderResponse,
    Direction,
    LimitOrderBody,
    LimitOrderResponse,
    MarketOrderBody,
    MarketOrderResponse,
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
        """Вспомогательный метод для маппинга строки из БД в OrderBase."""
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

    async def _map_row_to_any_order_response(
        self, order_row: Optional[dict]
    ) -> Optional[AnyOrderResponse]:
        """Маппинг строки из БД в соответствующую схему ответа (Market или Limit)."""
        if not order_row:
            return None

        order_dict = dict(order_row)

        has_price = order_dict.get("price") is not None
        direction = Direction(order_dict["direction"])
        ticker = order_dict["ticker"]
        qty = order_dict["qty"]
        user_id = order_dict["user_id"]
        order_id = order_dict["id"]
        status = OrderStatus(order_dict["status"])
        timestamp = order_dict["timestamp"]
        filled_qty = order_dict.get("filled_qty", 0)

        if has_price:
            price = order_dict["price"]
            order_body = LimitOrderBody(
                direction=direction, ticker=ticker, qty=qty, price=price
            )
            return LimitOrderResponse(
                id=order_id,
                user_id=user_id,
                status=status,
                timestamp=timestamp,
                body=order_body,
                filled=filled_qty,
            )
        else:
            order_body = MarketOrderBody(direction=direction, ticker=ticker, qty=qty)
            return MarketOrderResponse(
                id=order_id,
                user_id=user_id,
                status=status,
                timestamp=timestamp,
                body=order_body,
            )

    async def _get_order_from_db_by_id_mapped(
        self, order_id: uuid.UUID
    ) -> Optional[AnyOrderResponse]:
        """Загружает ордер из БД и мапит его в соответствующую схему ответа."""
        stmt = select(orders_table).where(orders_table.c.id == order_id)
        result = await self.db.execute(stmt)
        order_row = result.mappings().one_or_none()
        return await self._map_row_to_any_order_response(order_row)

    async def create_order(
        self, current_user: User, order_data: Union[MarketOrderBody, LimitOrderBody]
    ) -> CreateOrderResponse:
        """
        Создание ордера.
        Простые проверки, создание в БД, запуск матчинга.
        """
        order_id_obj = uuid.uuid4()
        user_id_obj = current_user.id
        price_value = getattr(order_data, "price", None)
        is_limit_order = isinstance(order_data, LimitOrderBody)

        if is_limit_order and price_value <= 0:
            raise ValueError("Price for limit order must be positive.")

        if order_data.qty <= 0:
            raise ValueError("Order quantity must be positive.")

        instrument_exists_stmt = select(func.count(instruments_table.c.id)).where(
            instruments_table.c.ticker == order_data.ticker
        )
        instrument_count_result = await self.db.execute(instrument_exists_stmt)
        count = instrument_count_result.scalar_one_or_none()
        if not count or count == 0:
            raise ValueError(
                f"Instrument with ticker '{order_data.ticker}' does not exist."
            )

        insert_stmt = insert(orders_table).values(
            id=order_id_obj,
            user_id=user_id_obj,
            ticker=order_data.ticker,
            direction=order_data.direction,
            qty=order_data.qty,
            price=price_value,
            status=OrderStatus.NEW,
            filled_qty=0,
        )
        await self.db.execute(insert_stmt)

        logger.info(
            f"Created order {order_id_obj}: {order_data.direction} {order_data.qty} {order_data.ticker}"
            + (f" @ {price_value}" if price_value else " (market)")
        )

        order_base = OrderBase(
            id=order_id_obj,
            user_id=user_id_obj,
            timestamp=datetime.now(timezone.utc),  
            direction=order_data.direction,
            ticker=order_data.ticker,
            qty=order_data.qty,
            price=price_value,
            status=OrderStatus.NEW,
            filled_qty=0,
        )

        try:
            await self.matching_engine.process_order(order_base, user_id_obj)
        except ValueError as e:
            logger.info(f"Order {order_id_obj} processing completed with business logic error: {e}")
        except Exception as e:
            logger.error(f"System error during order matching for {order_id_obj}: {e}")

        return CreateOrderResponse(order_id=order_id_obj)

    async def get_order_by_id_for_user(
        self, order_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[AnyOrderResponse]:
        stmt = select(orders_table).where(
            orders_table.c.id == order_id, orders_table.c.user_id == user_id
        )
        result = await self.db.execute(stmt)
        order_row = result.mappings().one_or_none()
        return await self._map_row_to_any_order_response(order_row)

    async def get_orders_by_user(
        self, user_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[AnyOrderResponse]:
        stmt = (
            select(orders_table)
            .where(orders_table.c.user_id == user_id)
            .order_by(orders_table.c.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        order_rows = result.mappings().all()

        orders = []
        for row in order_rows:
            order_response = await self._map_row_to_any_order_response(row)
            if order_response:
                orders.append(order_response)

        return orders

    async def cancel_order(self, order_id: uuid.UUID, current_user: User) -> bool:
        """
        Отменяет ордер пользователя. Упрощенная логика.
        """
        order = await self._get_order_from_db_by_id(order_id)

        if not order:
            raise ValueError("Order not found")

        if order.user_id != current_user.id:
            raise ValueError("Order does not belong to the current user")

        if order.status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]:
            raise ValueError(f"Cannot cancel order with status {order.status}")

        update_stmt = update(orders_table).where(
            orders_table.c.id == order_id
        ).values(status=OrderStatus.CANCELLED)
        
        await self.db.execute(update_stmt)

        logger.info(f"Cancelled order {order_id} for user {current_user.id}")
        return True
