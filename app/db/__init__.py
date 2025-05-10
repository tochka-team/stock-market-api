import logging
from sqlalchemy import text

from app.db.connection import async_engine

logger = logging.getLogger(__name__)

async def init_db():
    """Инициализация базы данных"""
    try:
        # Создаем таблицу orders
        async with async_engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    price INTEGER,
                    status TEXT NOT NULL,
                    filled INTEGER NOT NULL DEFAULT 0,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Создаем индексы для оптимизации запросов
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_orders_ticker_direction_status 
                ON orders(ticker, direction, status)
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_orders_user_id 
                ON orders(user_id)
            """))
            
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise
