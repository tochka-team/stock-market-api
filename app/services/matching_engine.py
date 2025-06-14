import logging
import uuid
from typing import Optional

from sqlalchemy import asc, desc, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.orders import orders_table
from app.db.models.transactions import transactions_table
from app.schemas.order import Direction, OrderBase, OrderStatus
from app.services.balance_service import BalanceService

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

        logger.info(
            f"MATCH_DEBUG: Finding match for order ID: {order_to_match.id}, Ticker: {order_to_match.ticker}, Direction: {order_to_match.direction}, Price: {order_to_match.price}, Qty: {order_to_match.qty}, Filled: {order_to_match.filled_qty}, UserID: {order_to_match.user_id}"
        )

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
        logger.info(f"MatchingEngine: Starting processing for new order {new_order_id}")

        current_new_order_state = await self._get_order_details(new_order_id)

        if not current_new_order_state:
            logger.warning(f"Order {new_order_id} not found in DB for matching.")
            return

        if (
            current_new_order_state.status
            not in [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]
            or (current_new_order_state.qty - current_new_order_state.filled_qty) <= 0
        ):
            logger.info(
                f"Order {new_order_id} is not in a matchable state initially. Status: {current_new_order_state.status}, Remaining: {(current_new_order_state.qty - current_new_order_state.filled_qty)}."
            )
            return

        # Запоминаем исходные заблокированные средства для market orders
        original_locked_amount = 0
        is_market_buy = (current_new_order_state.direction == Direction.BUY and 
                        current_new_order_state.price is None)
        
        if is_market_buy:
            # Получаем текущие заблокированные RUB
            rub_balance = await self.balance_service._get_or_create_balance_record(
                current_new_order_state.user_id, "RUB", create_if_not_exists=False
            )
            if rub_balance:
                original_locked_amount = rub_balance["locked_amount"]

        total_spent = 0  # Отслеживаем реально потраченные средства для market orders

        while (current_new_order_state.qty - current_new_order_state.filled_qty) > 0:
            logger.debug(
                f"Order {new_order_id}: Looking for a match. Remaining qty: {current_new_order_state.qty - current_new_order_state.filled_qty}"
            )

            counter_order = await self._find_best_match(current_new_order_state)

            if not counter_order:
                logger.info(
                    f"No further match found for order {new_order_id}. Order remains in book with remaining qty."
                )
                break

            trade_price: int
            if current_new_order_state.direction == Direction.BUY:
                trade_price = counter_order.price
            else:
                trade_price = counter_order.price

            remaining_qty_new = (
                current_new_order_state.qty - current_new_order_state.filled_qty
            )
            remaining_qty_counter = counter_order.qty - counter_order.filled_qty
            trade_qty = min(remaining_qty_new, remaining_qty_counter)

            if trade_qty <= 0:
                logger.warning(
                    f"Calculated trade_qty is {trade_qty} for new_order {current_new_order_state.id} and counter_order {counter_order.id}. Breaking match loop."
                )
                break

            logger.info(
                f"Attempting trade: New Order {current_new_order_state.id} ({current_new_order_state.direction} rem: {remaining_qty_new} @ {current_new_order_state.price}) "
                f"vs Counter Order {counter_order.id} ({counter_order.direction} rem: {remaining_qty_counter} @ {counter_order.price}). "
                f"Trade: {trade_qty} @ {trade_price}."
            )

            try:
                buyer_id = (
                    current_new_order_state.user_id
                    if current_new_order_state.direction == Direction.BUY
                    else counter_order.user_id
                )
                seller_id = (
                    current_new_order_state.user_id
                    if current_new_order_state.direction == Direction.SELL
                    else counter_order.user_id
                )

                await self.balance_service.execute_trade_balances(
                    buyer_id=buyer_id,
                    seller_id=seller_id,
                    ticker=current_new_order_state.ticker,
                    trade_qty=trade_qty,
                    trade_price=trade_price,
                )

                # Отслеживаем потраченные средства для market BUY orders
                if is_market_buy and current_new_order_state.user_id == buyer_id:
                    trade_cost = trade_qty * trade_price
                    total_spent += trade_cost
                    
                    # НЕМЕДЛЕННО корректируем заблокированные средства после каждой сделки
                    current_rub_balance = await self.balance_service._get_or_create_balance_record(
                        current_new_order_state.user_id, "RUB", create_if_not_exists=False
                    )
                    if current_rub_balance and current_rub_balance["locked_amount"] >= trade_cost:
                        # Уменьшаем locked amount на потраченную сумму
                        await self.balance_service.unblock_funds(
                            user_id=current_new_order_state.user_id,
                            ticker="RUB",
                            amount=trade_cost,
                        )
                        logger.info(f"Market BUY order {new_order_id}: released {trade_cost} RUB from locked amount after trade")
                    else:
                        logger.warning(f"Market BUY order {new_order_id}: insufficient locked RUB to release {trade_cost}")

                transaction_id = uuid.uuid4()
                insert_tx_stmt = insert(transactions_table).values(
                    id=transaction_id,
                    ticker=current_new_order_state.ticker,
                    amount=trade_qty,
                    price=trade_price,
                    buy_order_id=(
                        current_new_order_state.id
                        if current_new_order_state.direction == Direction.BUY
                        else counter_order.id
                    ),
                    sell_order_id=(
                        current_new_order_state.id
                        if current_new_order_state.direction == Direction.SELL
                        else counter_order.id
                    ),
                    buyer_user_id=buyer_id,
                    seller_user_id=seller_id,
                )
                await self.db.execute(insert_tx_stmt)
                logger.info(f"Created transaction {transaction_id} for trade.")

                new_order_filled_qty_after_trade = (
                    current_new_order_state.filled_qty + trade_qty
                )
                new_order_status_after_trade = (
                    OrderStatus.EXECUTED
                    if new_order_filled_qty_after_trade == current_new_order_state.qty
                    else OrderStatus.PARTIALLY_EXECUTED
                )

                update_new_order_stmt = (
                    update(orders_table)
                    .where(orders_table.c.id == current_new_order_state.id)
                    .values(
                        filled_qty=new_order_filled_qty_after_trade,
                        status=new_order_status_after_trade,
                    )
                )
                await self.db.execute(update_new_order_stmt)
                logger.info(
                    f"Updated new order {current_new_order_state.id}: filled_qty={new_order_filled_qty_after_trade}, status={new_order_status_after_trade.value}"
                )

                counter_order_filled_qty_after_trade = (
                    counter_order.filled_qty + trade_qty
                )
                counter_order_status_after_trade = (
                    OrderStatus.EXECUTED
                    if counter_order_filled_qty_after_trade == counter_order.qty
                    else OrderStatus.PARTIALLY_EXECUTED
                )

                update_counter_order_stmt = (
                    update(orders_table)
                    .where(orders_table.c.id == counter_order.id)
                    .values(
                        filled_qty=counter_order_filled_qty_after_trade,
                        status=counter_order_status_after_trade,
                    )
                )
                await self.db.execute(update_counter_order_stmt)
                logger.info(
                    f"Updated counter order {counter_order.id}: filled_qty became {counter_order_filled_qty_after_trade}, status={counter_order_status_after_trade.value}"
                )

                current_new_order_state.filled_qty = new_order_filled_qty_after_trade
                current_new_order_state.status = new_order_status_after_trade

                if current_new_order_state.status == OrderStatus.EXECUTED:
                    logger.info(f"Order {new_order_id} is now fully EXECUTED.")
                    break

            except Exception as e:
                logger.error(
                    f"CRITICAL ERROR during trade execution in loop for new_order {new_order_id} (counter_order: {counter_order.id if counter_order else 'N/A'}): {e}",
                    exc_info=True,
                )
                raise
                
        # Возвращаем оставшиеся неиспользованные средства для market BUY orders
        if is_market_buy:
            # Получаем текущий locked amount (он уже был скорректирован после каждой сделки)
            current_rub_balance = await self.balance_service._get_or_create_balance_record(
                current_new_order_state.user_id, "RUB", create_if_not_exists=False
            )
            if current_rub_balance and current_rub_balance["locked_amount"] > 0:
                remaining_locked = current_rub_balance["locked_amount"]
                logger.info(f"Returning {remaining_locked} remaining unused RUB for market BUY order {new_order_id}")
                try:
                    await self.balance_service.unblock_funds(
                        user_id=current_new_order_state.user_id,
                        ticker="RUB",
                        amount=remaining_locked,
                    )
                except Exception as e:
                    logger.error(f"Failed to return remaining unused funds for order {new_order_id}: {e}")
                    
        logger.info(
            f"MatchingEngine: Finished processing for order {new_order_id}. Final status: {current_new_order_state.status if current_new_order_state else 'N/A'}, Filled: {current_new_order_state.filled_qty if current_new_order_state else 'N/A'}"
        )
