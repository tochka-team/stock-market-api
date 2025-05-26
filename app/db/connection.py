import logging
from typing import AsyncGenerator

from fastapi import status
from fastapi.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.core.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)


async def get_db_connection() -> AsyncGenerator[AsyncConnection, None]:
    """
    Зависимость FastAPI для получения асинхронного соединения с базой данных,
    которое автоматически управляет транзакцией для всего запроса.
    """
    try:
        async with async_engine.connect() as connection:
            async with connection.begin():
                try:
                    yield connection
                except HTTPException:
                    raise
                except SQLAlchemyError as db_exc:
                    logger.error(
                        f"SQLAlchemyError during request, will rollback: {db_exc}",
                        exc_info=True,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Database operation failed.",
                    ) from db_exc
                except Exception as e:
                    logger.error(
                        f"Unexpected error during request, will rollback: {e}",
                        exc_info=True,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="An unexpected error occurred.",
                    ) from e
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to acquire DB connection or start transaction: {e}", exc_info=True
        )
        raise ConnectionError(
            "Could not connect to the database or start transaction."
        ) from e
    except Exception as e:
        logger.error(
            f"An unexpected error occurred in get_db_connection: {e}", exc_info=True
        )
        raise


async def check_db_connection():
    try:
        async with async_engine.connect():
            logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        raise ConnectionError(
            "Could not connect to the database during startup check."
        ) from e


async def close_db_connection():
    logger.info("Closing database connection pool.")
    await async_engine.dispose()
