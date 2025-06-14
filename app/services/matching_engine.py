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
        """Загружает полную информацию об ордере из базы данных по его ID."""
        stmt = select(orders_table).where(orders_table.c.id == order_id)
        result = await self.db.execute(stmt)
        order_row = result.mappings().one_or_none()

        if order_row:
            order_dict = dict(order_row)
            if "filled_qty" in order_dict and "filled" not in order_dict:
                order_dict["filled"] = order_dict.pop("filled_qty")
            return OrderBase.model_validate(order_dict)
        return None

    async def _get_best_ask_price(self, ticker: str) -> Optional[int]:
        """Получить лучшую цену ask"""
        stmt = select(orders_table.c.price).where(
            orders_table.c.ticker == ticker,
            orders_table.c.direction == Direction.SELL,
            orders_table.c.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]),
            orders_table.c.price.is_not(None),
            (orders_table.c.qty - orders_table.c.filled_qty) > 0
        ).order_by(asc(orders_table.c.price)).limit(1)
        
        result = await self.db.execute(stmt)
        return result.scalar()

    async def _find_best_match(self, order_to_match: OrderBase) -> Optional[OrderBase]:
        """
        Ищет лучший встречный активный ордер в стакане.
        """
        remaining_qty_to_match = order_to_match.qty - order_to_match.filled_qty
        if remaining_qty_to_match <= 0:
            return None

        base_query = select(orders_table).where(
            orders_table.c.ticker == order_to_match.ticker,
            orders_table.c.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]),
            (orders_table.c.qty - orders_table.c.filled_qty) > 0,
            orders_table.c.id != order_to_match.id
        )

        if order_to_match.direction == Direction.BUY:
            match_query = base_query.where(orders_table.c.direction == Direction.SELL)
            if order_to_match.price is not None:
                match_query = match_query.where(orders_table.c.price <= order_to_match.price)
            match_query = match_query.order_by(asc(orders_table.c.price), asc(orders_table.c.timestamp))

        elif order_to_match.direction == Direction.SELL:
            match_query = base_query.where(orders_table.c.direction == Direction.BUY)
            if order_to_match.price is not None:
                match_query = match_query.where(orders_table.c.price >= order_to_match.price)
            match_query = match_query.order_by(desc(orders_table.c.price), asc(orders_table.c.timestamp))

        else:
            return None

        best_match_stmt = match_query.limit(1)
        result = await self.db.execute(best_match_stmt)
        match_row = result.mappings().one_or_none()

        if match_row:
            order_dict = dict(match_row)
            if "filled_qty" in order_dict and "filled" not in order_dict:
                order_dict["filled"] = order_dict.pop("filled_qty")
            return OrderBase.model_validate(order_dict)

        return None

    async def process_order(self, order: OrderBase, user_id: uuid.UUID):
        ticker = order.ticker
        
        logger.info(f"Processing order {order.id}: {order.direction} {order.qty} {ticker} @ {order.price}")

        await self.balance_service._ensure_balance_exists(user_id, "RUB")
        await self.balance_service._ensure_balance_exists(user_id, ticker)

        user_rub_balance = await self.balance_service.get_balance(user_id, "RUB")
        user_ticker_balance = await self.balance_service.get_balance(user_id, ticker)

        if order.direction == Direction.BUY:
            if order.price is None:
                best_ask = await self._get_best_ask_price(ticker)
                if best_ask is None:
                    raise ValueError("No liquidity for market order")
                required_rub = order.qty * best_ask
            else:
                required_rub = order.qty * order.price

            if user_rub_balance < required_rub:
                raise ValueError(f"Insufficient RUB balance: {user_rub_balance} < {required_rub}")
        else:
            if user_ticker_balance < order.qty:
                raise ValueError(f"Insufficient {ticker} balance: {user_ticker_balance} < {order.qty}")

        if order.price is None:
            await self._execute_market_order(order, user_id)
        else:
            await self._execute_limit_order(order, user_id)

    async def _execute_market_order(self, order: OrderBase, user_id: uuid.UUID):
        """Исполнение market ордера"""
        ticker = order.ticker
        remaining_qty = order.qty

        opposite_direction = Direction.SELL if order.direction == Direction.BUY else Direction.BUY
        
        opposite_orders_stmt = select(orders_table).where(
            orders_table.c.ticker == ticker,
            orders_table.c.direction == opposite_direction,
            orders_table.c.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]),
            (orders_table.c.qty - orders_table.c.filled_qty) > 0
        ).order_by(
            asc(orders_table.c.price) if order.direction == Direction.BUY else desc(orders_table.c.price),
            asc(orders_table.c.timestamp)
        )

        result = await self.db.execute(opposite_orders_stmt)
        opposite_orders = [OrderBase.model_validate(dict(row)) for row in result.mappings()]

        if not opposite_orders:
            raise ValueError("No matching orders available for market execution")

        executed = False
        for opposite_order in opposite_orders:
            if remaining_qty <= 0:
                break

            available_qty = opposite_order.qty - opposite_order.filled_qty
            if available_qty <= 0:
                continue

            match_qty = min(remaining_qty, available_qty)
            match_price = opposite_order.price

            buyer_id = user_id if order.direction == Direction.BUY else opposite_order.user_id
            seller_id = user_id if order.direction == Direction.SELL else opposite_order.user_id

            await self.balance_service.execute_trade_atomic(
                buyer_id, seller_id, ticker, match_qty, match_price
            )

            await self._update_order_filled_qty(order.id, order.filled_qty + match_qty)
            await self._update_order_filled_qty(opposite_order.id, opposite_order.filled_qty + match_qty)

            await self._record_transaction(ticker, match_qty, match_price)

            order.filled_qty += match_qty
            opposite_order.filled_qty += match_qty
            remaining_qty -= match_qty
            executed = True

            if opposite_order.filled_qty >= opposite_order.qty:
                await self._update_order_status(opposite_order.id, OrderStatus.EXECUTED)
            else:
                await self._update_order_status(opposite_order.id, OrderStatus.PARTIALLY_EXECUTED)

        if remaining_qty == 0:
            await self._update_order_status(order.id, OrderStatus.EXECUTED)
        elif executed:
            await self._update_order_status(order.id, OrderStatus.PARTIALLY_EXECUTED)
        else:
            raise ValueError("Not enough liquidity for market order")

    async def _execute_limit_order(self, order: OrderBase, user_id: uuid.UUID):
        """Исполнение limit ордера"""
        ticker = order.ticker
        remaining_qty = order.qty

        opposite_direction = Direction.SELL if order.direction == Direction.BUY else Direction.BUY
        
        if order.direction == Direction.BUY:
            matching_orders_stmt = select(orders_table).where(
                orders_table.c.ticker == ticker,
                orders_table.c.direction == Direction.SELL,
                orders_table.c.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]),
                orders_table.c.price <= order.price,
                (orders_table.c.qty - orders_table.c.filled_qty) > 0
            ).order_by(asc(orders_table.c.price), asc(orders_table.c.timestamp))
        else:
            matching_orders_stmt = select(orders_table).where(
                orders_table.c.ticker == ticker,
                orders_table.c.direction == Direction.BUY,
                orders_table.c.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]),
                orders_table.c.price >= order.price,
                (orders_table.c.qty - orders_table.c.filled_qty) > 0
            ).order_by(desc(orders_table.c.price), asc(orders_table.c.timestamp))

        result = await self.db.execute(matching_orders_stmt)
        matching_orders = [OrderBase.model_validate(dict(row)) for row in result.mappings()]

        if not matching_orders:
            await self._update_order_status(order.id, OrderStatus.NEW)
            return

        for opposite_order in matching_orders:
            if remaining_qty <= 0:
                break

            available_qty = opposite_order.qty - opposite_order.filled_qty
            match_qty = min(remaining_qty, available_qty)
            match_price = opposite_order.price

            buyer_id = user_id if order.direction == Direction.BUY else opposite_order.user_id
            seller_id = user_id if order.direction == Direction.SELL else opposite_order.user_id

            await self.balance_service.execute_trade_atomic(
                buyer_id, seller_id, ticker, match_qty, match_price
            )

            await self._update_order_filled_qty(order.id, order.filled_qty + match_qty)
            await self._update_order_filled_qty(opposite_order.id, opposite_order.filled_qty + match_qty)

            await self._record_transaction(ticker, match_qty, match_price)

            order.filled_qty += match_qty
            opposite_order.filled_qty += match_qty
            remaining_qty -= match_qty

            if opposite_order.filled_qty >= opposite_order.qty:
                await self._update_order_status(opposite_order.id, OrderStatus.EXECUTED)
            else:
                await self._update_order_status(opposite_order.id, OrderStatus.PARTIALLY_EXECUTED)

        if order.filled_qty >= order.qty:
            await self._update_order_status(order.id, OrderStatus.EXECUTED)
        elif order.filled_qty > 0:
            await self._update_order_status(order.id, OrderStatus.PARTIALLY_EXECUTED)
        else:
            await self._update_order_status(order.id, OrderStatus.NEW)

    async def process_new_order(self, new_order_id: uuid.UUID):
        """Обработка нового ордера - адаптер для совместимости"""
        order = await self._get_order_details(new_order_id)
        if not order:
            logger.warning(f"Order {new_order_id} not found")
            return

        try:
            await self.process_order(order, order.user_id)
        except ValueError as e:
            logger.error(f"Order {new_order_id} cancelled due to: {e}")
            await self._update_order_status(new_order_id, OrderStatus.CANCELLED)
        except Exception as e:
            logger.error(f"System error processing order {new_order_id}: {e}")
            raise

    async def _update_order_status(self, order_id: uuid.UUID, status: OrderStatus):
        """Обновить статус ордера"""
        stmt = update(orders_table).where(orders_table.c.id == order_id).values(status=status)
        await self.db.execute(stmt)

    async def _update_order_filled_qty(self, order_id: uuid.UUID, filled_qty: int):
        """Обновить количество исполненных акций в ордере"""
        stmt = update(orders_table).where(orders_table.c.id == order_id).values(filled_qty=filled_qty)
        await self.db.execute(stmt)

    async def _record_transaction(self, ticker: str, qty: int, price: int):
        """Записать транзакцию"""
        stmt = insert(transactions_table).values(
            ticker=ticker,
            amount=qty,
            price=price
        )
        await self.db.execute(stmt)
