#

import asyncio
import logging
from uuid import uuid4

from sqlalchemy import text

from app.db.connection import async_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_test_instrument():
    """
    Добавляет тестовый инструмент и заявки в базу данных
    """
    try:
        async with async_engine.begin() as conn:
            # Сначала создадим тестового пользователя
            user_id = str(uuid4())
            await conn.execute(
                text(
                    """
                    INSERT INTO users (id, name, api_key, role)
                    VALUES (:id, :name, :api_key, :role)
                    ON CONFLICT (id) DO NOTHING
                """
                ),
                {
                    "id": user_id,
                    "name": "Test User",
                    "api_key": f"TOKEN_{uuid4()}",
                    "role": "USER",
                },
            )

            # Добавляем тестовый инструмент
            await conn.execute(
                text(
                    """
                    INSERT INTO instruments (ticker, name, description)
                    VALUES (:ticker, :name, :description)
                    ON CONFLICT (ticker) DO NOTHING
                """
                ),
                {
                    "ticker": "AAPP",
                    "name": "Apple Inc.",
                    "description": "Apple Inc. Common Stock",
                },
            )

            # Добавляем тестовые заявки с указанием user_id
            orders_query = text(
                """
                INSERT INTO orders (user_id, ticker, direction, price, qty, status)
                VALUES 
                    (:user_id, 'AAPL', 'BUY', 150, 100, 'NEW'),
                    (:user_id, 'AAPL', 'BUY', 149, 200, 'NEW'),
                    (:user_id, 'AAPL', 'SELL', 151, 150, 'NEW'),
                    (:user_id, 'AAPL', 'SELL', 151, 300, 'NEW')
                ON CONFLICT DO NOTHING
            """
            )

            await conn.execute(orders_query, {"user_id": user_id})
            logger.info("Successfully added test user, instrument and orders")

    except Exception as e:
        logger.error(f"Error adding test data: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(add_test_instrument())
