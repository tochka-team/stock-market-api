import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)


async def get_db_connection() -> AsyncGenerator[AsyncConnection, None]:
    try:
        async with async_engine.connect() as connection:
            logger.debug(f"Connection acquired from pool: {connection}")
            try:
                yield connection
            except SQLAlchemyError as e:
                logger.error(
                    f"SQLAlchemy error during request: {e}", exc_info=True)
                raise
            finally:
                logger.debug(f"Connection released back to pool: {connection}")
    except SQLAlchemyError as e:
        logger.error(f"Failed to acquire DB connection: {e}", exc_info=True)
        raise ConnectionError("Could not connect to the database.") from e
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during DB connection handling: {e}", exc_info=True)
        raise


async def check_db_connection():
    try:
        async with async_engine.connect():
            logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        raise ConnectionError(
            "Could not connect to the database during startup check.") from e


async def close_db_connection():
    logger.info("Closing database connection pool.")
    await async_engine.dispose()
