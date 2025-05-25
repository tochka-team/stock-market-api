import logging
import uuid
from typing import List, Optional, Union

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.orders import orders_table
from app.schemas.order import LimitOrderBody, MarketOrderBody, OrderBase, OrderStatus
from app.schemas.user import User

logger = logging.getLogger(__name__)


class OrderService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def create_order(
        self, current_user: User, order_data: Union[MarketOrderBody, LimitOrderBody]
    ) -> OrderBase:
        """
        Создает новый ордер в базе данных.
        Пока без проверки баланса и без запуска matching engine.
        """
        order_id_obj = uuid.uuid4()
        user_id_obj = current_user.id

        price_value = None
        if isinstance(order_data, LimitOrderBody):
            price_value = order_data.price

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
            async with self.db.begin():
                result = await self.db.execute(insert_stmt)

            created_order_row = result.mappings().one_or_none()

            if not created_order_row:
                logger.error(
                    f"Order creation failed for user {user_id_obj}, no row returned."
                )
                raise Exception("Order creation failed unexpectedly.")

            order_dict = dict(created_order_row)
            if "filled_qty" in order_dict and "filled" not in order_dict:
                order_dict["filled"] = order_dict.pop("filled_qty")

            return OrderBase.model_validate(order_dict)

        except Exception as e:
            logger.error(
                f"Error creating order for user {user_id_obj}: {e}", exc_info=True
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
