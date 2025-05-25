import logging
import uuid
from typing import List, Optional, Union

from sqlalchemy import insert, select, update
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
        logger.debug(f"OrderService.create_order: DB connection {self.db}, in_transaction: {self.db.in_transaction()}")
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
    
    async def cancel_order(
        self,
        order_id: uuid.UUID,
        current_user: User
    ) -> bool:
        """
        Отменяет ордер пользователя.
        - Проверяет, что ордер принадлежит пользователю.
        - Проверяет, что ордер находится в отменяемом статусе.
        - Устанавливает статус ордера на CANCELLED.
        - Пока НЕ разблокирует средства (это будет на следующем этапе).
        Возвращает True, если ордер успешно отменен, иначе выбрасывает исключение.
        """
        user_id = current_user.id
        logger.debug(f"Attempting to cancel order {order_id} for user {user_id}")

        get_order_stmt = select(
            orders_table.c.id,
            orders_table.c.user_id,
            orders_table.c.status
        ).where(orders_table.c.id == order_id)
        
        order_res = await self.db.execute(get_order_stmt)
        order_to_cancel = order_res.mappings().one_or_none()

        if not order_to_cancel:
            logger.warning(f"Order {order_id} not found for cancellation by user {user_id}.")
            raise ValueError(f"Order with ID '{order_id}' not found.")

        if order_to_cancel["user_id"] != user_id:
            logger.warning(f"User {user_id} attempted to cancel order {order_id} owned by {order_to_cancel['user_id']}.")
            raise PermissionError("User not authorized to cancel this order.")

        current_status = order_to_cancel["status"]
        if current_status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]:
            logger.warning(f"Order {order_id} cannot be cancelled due to its status: {current_status}.")
            raise ValueError(f"Order cannot be cancelled. Current status: {current_status}.")

        update_stmt = update(orders_table).where(
            orders_table.c.id == order_id
        ).values(
            status=OrderStatus.CANCELLED,
        ).returning(orders_table.c.id)

        result = await self.db.execute(update_stmt)
        updated_id = result.scalar_one_or_none()

        if updated_id:
            logger.info(f"Order {order_id} successfully cancelled by user {user_id}.")
            return True
        else:
            logger.error(f"Failed to update status for order {order_id} during cancellation.")
            return False
