from typing import List
import logging

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection
from asyncpg.exceptions import UniqueViolationError

from app.db.models.instruments import instruments_table
from app.schemas.instrument import Instrument


logger = logging.getLogger(__name__)

class InstrumentService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def get_all_instruments(self) -> List[Instrument]:
        """
        Получает список всех торговых инструментов из базы данных.
        """
        select_stmt = select(
            instruments_table.c.id,
            instruments_table.c.name,
            instruments_table.c.ticker,
            instruments_table.c.description,
        )
        result = await self.db.execute(select_stmt)
        instrument_rows = result.mappings().all()
        instruments = [Instrument.model_validate(row) for row in instrument_rows]
        return instruments

    async def add_new_instrument(self, instrument_data: Instrument) -> Instrument:
        """
        Добавляет новый торговый инструмент в базу данных.
        `instrument_data` - это Pydantic модель Instrument, но используемая для создания.
        """
        insert_stmt = (
            insert(instruments_table)
            .values(
                ticker=instrument_data.ticker,
                name=instrument_data.name,
            )
            .returning(
                instruments_table.c.id,
                instruments_table.c.name,
                instruments_table.c.ticker,
                instruments_table.c.description,
            )
        )
        try:
            await self.db.execute(insert_stmt)
            logger.info(f"Instrument '{instrument_data.ticker}' added successfully.")
            return True
        except IntegrityError as e:
            error_detail = str(e.orig).lower() if hasattr(e, 'orig') and e.orig is not None else str(e).lower()

            is_pg_unique_violation = (hasattr(e, 'orig') and isinstance(e.orig, UniqueViolationError)) or \
                                     ("unique constraint" in error_detail and "violates" in error_detail) or \
                                     ("duplicate key value violates unique constraint" in error_detail)

            is_sqlite_unique_violation = "unique constraint failed: instruments.ticker" in error_detail

            if is_pg_unique_violation or is_sqlite_unique_violation:
                logger.warning(f"Attempt to add duplicate instrument ticker: {instrument_data.ticker}")
                raise ValueError(
                    f"Instrument with ticker '{instrument_data.ticker}' already exists."
                )
            logger.error(f"IntegrityError during instrument add: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during instrument add: {e}", exc_info=True)
            raise

    async def delete_instrument_by_ticker(self, ticker: str) -> bool:
        """
        Удаляет торговый инструмент по его тикеру.
        Возвращает True, если удаление успешно, False - если инструмент не найден.
        """
        delete_stmt = (
            delete(instruments_table)
            .where(instruments_table.c.ticker == ticker)
            .returning(instruments_table.c.id)
        )

        result = await self.db.execute(delete_stmt)

        deleted_id = result.scalar_one_or_none()
        return deleted_id is not None
