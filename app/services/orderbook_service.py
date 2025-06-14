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
            instrument_exists_stmt = select(
                func.count(instruments_table.c.ticker)
            ).where(instruments_table.c.ticker == ticker)
            instrument_count = await self.db.scalar(instrument_exists_stmt)

            if instrument_count == 0:
                return None

            buy_stmt = (
                select(
                    orders_table.c.price,
                    func.sum(orders_table.c.qty - orders_table.c.filled_qty).label(
                        "total_qty"
                    ),
                )
                .where(
                    orders_table.c.ticker == ticker,
                    orders_table.c.direction == Direction.BUY.value,
                    orders_table.c.status.in_(
                        [OrderStatus.NEW.value, OrderStatus.PARTIALLY_EXECUTED.value]
                    ),
                    (orders_table.c.qty - orders_table.c.filled_qty) > 0,
                )
                .group_by(orders_table.c.price)
                .order_by(desc(orders_table.c.price))
                .limit(limit)
            )

            sell_stmt = (
                select(
                    orders_table.c.price,
                    func.sum(orders_table.c.qty - orders_table.c.filled_qty).label(
                        "total_qty"
                    ),
                )
                .where(
                    orders_table.c.ticker == ticker,
                    orders_table.c.direction == Direction.SELL.value,
                    orders_table.c.status.in_(
                        [OrderStatus.NEW.value, OrderStatus.PARTIALLY_EXECUTED.value]
                    ),
                    (orders_table.c.qty - orders_table.c.filled_qty) > 0,
                )
                .group_by(orders_table.c.price)
                .order_by(asc(orders_table.c.price))
                .limit(limit)
            )

            bids_result = await self.db.execute(buy_stmt)
            bid_rows = bids_result.mappings().all()

            asks_result = await self.db.execute(sell_stmt)
            ask_rows = asks_result.mappings().all()

            bid_levels = [
                Level(price=row["price"], qty=row["total_qty"])
                for row in bid_rows
                if row["price"] is not None and row["total_qty"] > 0
            ]
            ask_levels = [
                Level(price=row["price"], qty=row["total_qty"])
                for row in ask_rows
                if row["price"] is not None and row["total_qty"] > 0
            ]

            return L2OrderBook(bid_levels=bid_levels, ask_levels=ask_levels)
        except Exception as e:
            print(f"Error in get_orderbook service: {e}")
            raise
