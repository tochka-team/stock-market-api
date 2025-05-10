import random
from typing import Optional, List
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.schemas.orderbook import L2OrderBook, Level

class OrderBookService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def get_orderbook(self, ticker: str, limit: int = 10) -> Optional[L2OrderBook]:
        """
        Получить стакан заявок для указанного тикера
        """
        try:
            # Проверяем существование инструмента
            instrument_query = text("""
                SELECT ticker FROM instruments WHERE ticker = :ticker
            """)
            instrument_result = await self.db.execute(instrument_query, {"ticker": ticker})
            if not instrument_result.scalar_one_or_none():
                return None

            # Получаем активные лимитные заявки на покупку (bids)
            bids_query = text("""
                SELECT price, qty 
                FROM orders 
                WHERE ticker = :ticker 
                AND direction = 'BUY' 
                AND status = 'NEW'
                ORDER BY price DESC 
                LIMIT :limit
            """)
            
            bids_result = await self.db.execute(bids_query, {"ticker": ticker, "limit": limit})
            bids = bids_result.mappings().all()
            
            # Получаем активные лимитные заявки на продажу (asks)
            asks_query = text("""
                SELECT price, qty 
                FROM orders 
                WHERE ticker = :ticker 
                AND direction = 'SELL' 
                AND status = 'NEW'
                ORDER BY price ASC 
                LIMIT :limit
            """)
            
            asks_result = await self.db.execute(asks_query, {"ticker": ticker, "limit": limit})
            asks = asks_result.mappings().all()
            
            # Агрегируем заявки по ценам
            bid_levels = self._aggregate_levels(bids)
            ask_levels = self._aggregate_levels(asks)
            
            return L2OrderBook(
                bid_levels=bid_levels,
                ask_levels=ask_levels
            )
        except Exception as e:
            print(f"Error getting orderbook: {e}")
            return None

    def _aggregate_levels(self, orders: List[dict]) -> List[Level]:
        """
        Агрегирует заявки по ценам, суммируя количество
        """
        levels = {}
        for order in orders:
            price = order['price']
            qty = order['qty']
            if price in levels:
                levels[price] += qty
            else:
                levels[price] = qty
        
        return [Level(price=price, qty=qty) for price, qty in levels.items()] 