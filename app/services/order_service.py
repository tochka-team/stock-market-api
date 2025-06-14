import logging
import uuid
from typing import List, Optional, Union

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
            # Limit Order - включаем поле filled
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
            # Market Order - БЕЗ поля filled согласно OpenAPI
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

    async def _estimate_market_order_cost(
        self, ticker: str, direction: Direction, qty: int
    ) -> int:
        """
        Оценивает стоимость market ордера на основе текущего orderbook.
        Для BUY orders - суммирует ask'и начиная с самых дешевых.
        Для SELL orders - возвращает количество активов для блокировки.
        """
        if direction == Direction.SELL:
            # Для продажи блокируем количество активов
            logger.debug(f"MARKET_ESTIMATE: SELL order for {qty} {ticker} - blocking {qty} assets")
            return qty
            
        # Для покупки ищем лучшие ask цены
        ask_stmt = (
            select(orders_table.c.price, (orders_table.c.qty - orders_table.c.filled_qty).label("available_qty"))
            .where(
                orders_table.c.ticker == ticker,
                orders_table.c.direction == Direction.SELL,
                orders_table.c.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]),
                orders_table.c.price.is_not(None),
                (orders_table.c.qty - orders_table.c.filled_qty) > 0
            )
            .order_by(orders_table.c.price.asc(), orders_table.c.timestamp.asc())
        )
        
        result = await self.db.execute(ask_stmt)
        asks = result.mappings().all()
        
        logger.debug(f"MARKET_ESTIMATE: Found {len(asks)} ask levels for {ticker}")
        
        if not asks:
            # Если нет предложений, используем высокую оценку для безопасности
            # Можно использовать последнюю цену сделки или фиксированное значение
            safety_estimate = qty * 1000  # Безопасная оценка
            logger.warning(f"MARKET_ESTIMATE: No asks available for market BUY of {ticker}, using safety estimate: {safety_estimate} RUB")
            return safety_estimate
            
        total_cost = 0
        remaining_qty = qty
        cost_breakdown = []
        
        for ask in asks:
            if remaining_qty <= 0:
                break
                
            available = min(ask["available_qty"], remaining_qty)
            cost_for_this_level = available * ask["price"]
            total_cost += cost_for_this_level
            remaining_qty -= available
            cost_breakdown.append(f"{available}@{ask['price']}={cost_for_this_level}")
            
        if remaining_qty > 0:
            # Если не хватает liquidity, добавляем буфер для оставшегося количества
            last_price = asks[-1]["price"] if asks else 1000
            buffer_cost = remaining_qty * last_price * 2  # 2x буфер для безопасности
            total_cost += buffer_cost
            cost_breakdown.append(f"{remaining_qty}@{last_price}x2={buffer_cost}(buffer)")
            logger.warning(f"MARKET_ESTIMATE: Insufficient liquidity for {remaining_qty} {ticker}, added buffer")
            
        logger.debug(f"MARKET_ESTIMATE: BUY {qty} {ticker} breakdown: {', '.join(cost_breakdown)} = total {total_cost} RUB")
        return total_cost

    async def create_order(
        self, current_user: User, order_data: Union[MarketOrderBody, LimitOrderBody]
    ) -> CreateOrderResponse:
        order_id_obj = uuid.uuid4()
        user_id_obj = current_user.id
        price_value = getattr(order_data, "price", None)
        is_limit_order = isinstance(order_data, LimitOrderBody)

        if is_limit_order:
            price_value = order_data.price
            if price_value <= 0:
                raise ValueError("Price for limit order must be positive.")

        if order_data.qty <= 0:
            raise ValueError("Order quantity must be positive.")

        # Проверяем существование инструмента
        instrument_exists_stmt = select(func.count(instruments_table.c.id)).where(
            instruments_table.c.ticker == order_data.ticker
        )
        instrument_count_result = await self.db.execute(instrument_exists_stmt)
        count = instrument_count_result.scalar_one_or_none()
        if not count or count == 0:
            raise ValueError(
                f"Instrument with ticker '{order_data.ticker}' does not exist."
            )

        ticker_to_block = ""
        amount_to_block = 0

        if order_data.direction == Direction.BUY:
            ticker_to_block = "RUB"
            if is_limit_order:
                amount_to_block = price_value * order_data.qty
            else:
                # Market BUY - оцениваем стоимость по orderbook
                amount_to_block = await self._estimate_market_order_cost(
                    order_data.ticker, Direction.BUY, order_data.qty
                )
                logger.info(f"Market BUY order estimated cost: {amount_to_block} RUB for {order_data.qty} {order_data.ticker}")

        elif order_data.direction == Direction.SELL:
            ticker_to_block = order_data.ticker
            if is_limit_order:
                amount_to_block = order_data.qty
            else:
                # Market SELL - блокируем активы
                amount_to_block = await self._estimate_market_order_cost(
                    order_data.ticker, Direction.SELL, order_data.qty
                )
                logger.info(f"Market SELL order blocking: {amount_to_block} {order_data.ticker}")

        # Блокируем средства
        if amount_to_block > 0:
            blocked_successfully = await self.balance_service.block_funds(
                user_id=user_id_obj,
                ticker=ticker_to_block,
                amount=amount_to_block,
            )
            if not blocked_successfully:
                raise ValueError(
                    f"Insufficient balance of {ticker_to_block} to place order."
                )
        else:
            logger.warning(f"Zero amount to block for order {order_id_obj}, this might be an issue")

        # Создаем ордер в БД
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

        created_order_id_from_db = None
        try:
            result = await self.db.execute(insert_stmt)
            created_order_id_from_db = result.scalar_one()

            if not created_order_id_from_db:
                raise Exception("Order creation failed (no ID returned).")

            await self.matching_engine.process_new_order(created_order_id_from_db)
            logger.info(f"Matching engine processed order {created_order_id_from_db}")

            return CreateOrderResponse(order_id=created_order_id_from_db)

        except Exception as e:
            logger.error(
                f"Error in create_order service for user {user_id_obj}: {e}",
                exc_info=True,
            )
            raise

    async def get_order_by_id_for_user(
        self, order_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[AnyOrderResponse]:
        stmt = select(orders_table).where(
            (orders_table.c.id == order_id) & (orders_table.c.user_id == user_id)
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

        orders_list = []
        for row in order_rows:
            mapped_order = await self._map_row_to_any_order_response(row)
            if mapped_order:
                orders_list.append(mapped_order)
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

        remaining_qty_to_unblock = (
            order_to_cancel_row["qty"] - order_to_cancel_row["filled_qty"]
        )

        if remaining_qty_to_unblock > 0:
            amount_to_unblock = 0
            ticker_to_unblock = ""
            
            if order_to_cancel_row["direction"] == Direction.BUY:
                ticker_to_unblock = "RUB"
                if order_to_cancel_row["price"] is not None:
                    # Limit order - точно знаем сколько заблокировано
                    amount_to_unblock = order_to_cancel_row["price"] * remaining_qty_to_unblock
                else:
                    # Market order - нужно посчитать заблокированные средства
                    rub_balance = await self.balance_service.get_balance(
                        user_id, "RUB"
                    )
                    if rub_balance and rub_balance["locked_amount"] > 0:
                        amount_to_unblock = rub_balance["locked_amount"]
                        logger.info(f"Market BUY order {order_id}: unblocking all locked RUB amount: {amount_to_unblock}")
                    else:
                        logger.warning(f"Market BUY order {order_id}: no locked RUB found to unblock")
                        
            elif order_to_cancel_row["direction"] == Direction.SELL:
                ticker_to_unblock = order_to_cancel_row["ticker"]
                amount_to_unblock = remaining_qty_to_unblock

            if ticker_to_unblock and amount_to_unblock > 0:
                await self.balance_service.unblock_funds(
                    user_id=user_id,
                    ticker=ticker_to_unblock,
                    amount=amount_to_unblock,
                )
                logger.info(f"Successfully unblocked {amount_to_unblock} {ticker_to_unblock} for cancelled order {order_id}")
            else:
                logger.info(f"No funds to unblock for order {order_id}")

        # Обновляем статус ордера на CANCELLED
        update_stmt = (
            update(orders_table)
            .where(orders_table.c.id == order_id)
            .values(status=OrderStatus.CANCELLED)
            .returning(orders_table.c.id)
        )
        result = await self.db.execute(update_stmt)
        updated_id = result.scalar_one_or_none()

        if updated_id:
            logger.info(f"Order {order_id} successfully cancelled and funds unblocked by user {user_id}.")
            return True
        else:
            raise Exception("Failed to update order status after unblocking funds.")
