from typing import Optional

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.instruments import instruments_table
from app.db.models.orders import orders_table
from app.schemas.order import Direction, OrderStatus
from app.schemas.orderbook import L2OrderBook, Level


class OrderBookService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def get_orderbook(
        self, ticker: str, limit: int = 10
    ) -> Optional[L2OrderBook]:
        """
        Получить стакан заявок для указанного тикера, используя SQLAlchemy Core.
        """
        try:
            # Проверяем существование инструмента
            instrument_exists_stmt = select(func.count(instruments_table.c.id)).where(
                instruments_table.c.ticker == ticker
            )

            instrument_count_result = await self.db.execute(instrument_exists_stmt)
            count = instrument_count_result.scalar_one_or_none()

            if not count or count == 0:
                return None

            # Получаем активные лимитные заявки на покупку (bids)
            remaining_qty = orders_table.c.qty - orders_table.c.filled_qty

            bids_stmt = (
                select(orders_table.c.price, func.sum(remaining_qty).label("total_qty"))
                .where(
                    orders_table.c.ticker == ticker,
                    orders_table.c.direction == Direction.BUY,
                    orders_table.c.status.in_(
                        [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]
                    ),
                    orders_table.c.price.is_not(None),
                )
                .group_by(orders_table.c.price)
                .order_by(
                    # Лучшие цены покупки (самые высокие) идут первыми
                    desc(orders_table.c.price)
                )
                .limit(limit)
            )

            bids_result = await self.db.execute(bids_stmt)
            bid_rows = bids_result.mappings().all()

            # Получаем активные лимитные заявки на продажу (asks)
            asks_stmt = (
                select(orders_table.c.price, func.sum(remaining_qty).label("total_qty"))
                .where(
                    orders_table.c.ticker == ticker,
                    orders_table.c.direction == Direction.SELL,
                    orders_table.c.status.in_(
                        [OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED]
                    ),
                    orders_table.c.price.is_not(None),
                )
                .group_by(orders_table.c.price)
                .order_by(asc(orders_table.c.price))
                .limit(limit)
            )

            asks_result = await self.db.execute(asks_stmt)
            ask_rows = asks_result.mappings().all()

            # Формируем уровни для Pydantic схемы
            bid_levels = [
                Level(price=row["price"], qty=row["total_qty"])
                for row in bid_rows
                if row["price"] is not None
            ]
            ask_levels = [
                Level(price=row["price"], qty=row["total_qty"])
                for row in ask_rows
                if row["price"] is not None
            ]

            return L2OrderBook(bid_levels=bid_levels, ask_levels=ask_levels)
        except Exception as e:
            print(f"Error in get_orderbook service: {e}")
            raise
