import logging
import uuid
from typing import Optional

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.orders import orders_table
from app.schemas.order import Direction, OrderBase, OrderStatus

logger = logging.getLogger(__name__)


class MatchingEngine:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def _get_order_details(self, order_id: uuid.UUID) -> Optional[OrderBase]:
        """
        Загружает полную информацию об ордере из базы данных по его ID.
        """
        stmt = select(orders_table).where(orders_table.c.id == order_id)
        result = await self.db.execute(stmt)
        order_row = result.mappings().one_or_none()

        if order_row:
            order_dict = dict(order_row)
            if "filled_qty" in order_dict and "filled" not in order_dict:
                order_dict["filled"] = order_dict.pop("filled_qty")
            return OrderBase.model_validate(order_dict)
        return None

    async def _find_best_match(self, order_to_match: OrderBase) -> Optional[OrderBase]:
        """
        Ищет лучший встречный активный ордер в стакане.
        - Для BUY ордера: ищет самый дешевый SELL ордер (price ASC, timestamp ASC).
        - Для SELL ордера: ищет самый дорогой BUY ордер (price DESC, timestamp ASC).
        Учитывает только ордера со статусом NEW или PARTIALLY_EXECUTED и неисполненным остатком.
        """
        remaining_qty_to_match = order_to_match.qty - order_to_match.filled_qty
        if remaining_qty_to_match <= 0:
            logger.debug(
                f"Order {order_to_match.id} is already filled. No match finding needed."
            )
            return None

        base_query = select(orders_table).where(
            orders_table.c.ticker == order_to_match.ticker,
            orders_table.c.status.in_(
                [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]
            ),
            (orders_table.c.qty - orders_table.c.filled_qty) > 0,
            orders_table.c.user_id != order_to_match.user_id,
            orders_table.c.id != order_to_match.id,
        )

        match_query = None
        if order_to_match.direction == Direction.BUY:
            match_query = base_query.where(orders_table.c.direction == Direction.SELL)
            if order_to_match.price is not None:
                match_query = match_query.where(
                    orders_table.c.price <= order_to_match.price
                )

            match_query = match_query.order_by(
                asc(orders_table.c.price), asc(orders_table.c.timestamp)
            )

        elif order_to_match.direction == Direction.SELL:
            match_query = base_query.where(orders_table.c.direction == Direction.BUY)
            if order_to_match.price is not None:
                match_query = match_query.where(
                    orders_table.c.price >= order_to_match.price
                )

            match_query = match_query.order_by(
                desc(orders_table.c.price), asc(orders_table.c.timestamp)
            )

        if match_query is None:
            logger.error(
                f"Could not determine match query for order {order_to_match.id} with direction {order_to_match.direction}"
            )
            return None

        best_match_stmt = match_query.limit(1)

        result = await self.db.execute(best_match_stmt)
        match_row = result.mappings().one_or_none()

        if match_row:
            logger.debug(
                f"Found potential match for order {order_to_match.id}: order {match_row['id']}"
            )
            order_dict = dict(match_row)
            if "filled_qty" in order_dict and "filled" not in order_dict:
                order_dict["filled"] = order_dict.pop("filled_qty")
            return OrderBase.model_validate(order_dict)

        logger.debug(
            f"No suitable match found in order book for order {order_to_match.id}"
        )
        return None

    async def process_new_order(self, new_order_id: uuid.UUID):
        """
        Обрабатывает новый ордер, пытаясь свести его с существующими в стакане.
        """
        logger.info(f"MatchingEngine: Processing new order {new_order_id}")

        new_order = await self._get_order_details(new_order_id)

        if not new_order:
            logger.warning(f"Order {new_order_id} not found in DB for matching.")
            return

        if new_order.status != OrderStatus.NEW:
            logger.info(
                f"Order {new_order_id} is not in a matchable state (status: {new_order.status}). Skipping matching."
            )
            return

        remaining_qty_new_order = new_order.qty - new_order.filled_qty
        if remaining_qty_new_order <= 0:
            logger.info(f"Order {new_order_id} has no remaining quantity to match.")
            return

        best_counter_order = await self._find_best_match(new_order)

        if best_counter_order:
            logger.info(
                f"Match found for order {new_order.id} (qty: {remaining_qty_new_order}, price: {new_order.price}, dir: {new_order.direction}) "
                f"with counter order {best_counter_order.id} (qty: {best_counter_order.qty - best_counter_order.filled_qty}, price: {best_counter_order.price}, dir: {best_counter_order.direction}). "
                f"TODO: Execute trade logic."
            )
        else:
            logger.info(
                f"No match found for order {new_order.id}. It remains in the order book."
            )
