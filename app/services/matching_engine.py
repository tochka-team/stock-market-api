import logging
import uuid
from typing import Optional

from sqlalchemy import asc, desc, select, update, insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.orders import orders_table
from app.db.models.transactions import transactions_table
from app.services.balance_service import BalanceService
from app.schemas.order import Direction, OrderBase, OrderStatus

logger = logging.getLogger(__name__)


class MatchingEngine:
    def __init__(self, db: AsyncConnection):
        self.db = db
        self.balance_service = BalanceService(db)

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
        
        logger.info(f"MATCH_DEBUG: Finding match for order ID: {order_to_match.id}, Ticker: {order_to_match.ticker}, Direction: {order_to_match.direction}, Price: {order_to_match.price}, Qty: {order_to_match.qty}, Filled: {order_to_match.filled_qty}, UserID: {order_to_match.user_id}")

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

    async def process_new_order(self, new_order_id: uuid.UUID):
        logger.info(f"MatchingEngine: Processing new order {new_order_id}")
        new_order = await self._get_order_details(new_order_id)

        if not new_order or \
           new_order.status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED] or \
           (new_order.qty - new_order.filled_qty) <= 0:
            logger.info(f"Order {new_order_id} is not in a matchable state. Status: {new_order.status if new_order else 'N/A'}, Remaining: {(new_order.qty - new_order.filled_qty) if new_order else 'N/A'}.")
            return
        
        counter_order = await self._find_best_match(new_order)

        if counter_order:
            trade_price: int
            if new_order.direction == Direction.BUY:
                trade_price = counter_order.price 
            else:
                trade_price = counter_order.price

            remaining_qty_new = new_order.qty - new_order.filled_qty
            remaining_qty_counter = counter_order.qty - counter_order.filled_qty
            trade_qty = min(remaining_qty_new, remaining_qty_counter)

            if trade_qty <= 0:
                logger.warning(f"Calculated trade_qty is {trade_qty} for new_order {new_order.id} and counter_order {counter_order.id}. Skipping trade.")
                return

            logger.info(
                f"Attempting trade: New Order {new_order.id} ({new_order.direction} {remaining_qty_new} {new_order.ticker} @ {new_order.price}) "
                f"vs Counter Order {counter_order.id} ({counter_order.direction} {remaining_qty_counter} {counter_order.ticker} @ {counter_order.price}). "
                f"Trade: {trade_qty} @ {trade_price}."
            )

           
            try:
                buyer_id = new_order.user_id if new_order.direction == Direction.BUY else counter_order.user_id
                seller_id = new_order.user_id if new_order.direction == Direction.SELL else counter_order.user_id
                
                await self.balance_service.execute_trade_balances(
                    buyer_id=buyer_id,
                    seller_id=seller_id,
                    ticker=new_order.ticker,
                    trade_qty=trade_qty,
                    trade_price=trade_price
                )

                transaction_id = uuid.uuid4()
                insert_tx_stmt = insert(transactions_table).values(
                    id=transaction_id,
                    ticker=new_order.ticker,
                    amount=trade_qty,
                    price=trade_price,
                    buy_order_id = new_order.id if new_order.direction == Direction.BUY else counter_order.id,
                    sell_order_id = new_order.id if new_order.direction == Direction.SELL else counter_order.id,
                    buyer_user_id = buyer_id,
                    seller_user_id = seller_id
                )
                await self.db.execute(insert_tx_stmt)
                logger.info(f"Created transaction {transaction_id} for trade.")

                new_order.filled_qty += trade_qty
                new_order_status = OrderStatus.EXECUTED if new_order.filled_qty == new_order.qty else OrderStatus.PARTIALLY_EXECUTED
                
                update_new_order_stmt = update(orders_table).where(
                    orders_table.c.id == new_order.id
                ).values(
                    filled_qty=new_order.filled_qty,
                    status=new_order_status
                )
                await self.db.execute(update_new_order_stmt)
                logger.info(f"Updated new order {new_order.id}: filled_qty={new_order.filled_qty}, status={new_order_status.value}")

                counter_order.filled_qty += trade_qty
                counter_order_status = OrderStatus.EXECUTED if counter_order.filled_qty == counter_order.qty else OrderStatus.PARTIALLY_EXECUTED
                
                update_counter_order_stmt = update(orders_table).where(
                    orders_table.c.id == counter_order.id
                ).values(
                    filled_qty=orders_table.c.filled_qty + trade_qty,
                    status=counter_order_status
                )
                await self.db.execute(update_counter_order_stmt)
                logger.info(f"Updated counter order {counter_order.id}: filled_qty increased by {trade_qty}, status={counter_order_status.value}")


            except Exception as e:
                logger.error(f"CRITICAL ERROR during trade execution between {new_order.id} and {counter_order.id}: {e}", exc_info=True)
                raise
        else:
            logger.info(f"No match found for order {new_order.id}. It remains in the order book.")
