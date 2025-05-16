# app/services/instrument_service.py
from typing import List

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.instruments import instruments_table
from app.schemas.instrument import Instrument


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
            async with self.db.begin():
                result = await self.db.execute(insert_stmt)
            created_instrument_row = result.mappings().one_or_none()

            if created_instrument_row is None:
                raise Exception("Instrument creation failed, no row returned.")

            return Instrument.model_validate(created_instrument_row)
        except IntegrityError as e:
            if "UNIQUE constraint failed: instruments.ticker" in str(
                e
            ) or "uq_instruments_ticker" in str(e):
                raise ValueError(
                    f"Instrument with ticker '{instrument_data.ticker}' already exists."
                )
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

        async with self.db.begin():
            result = await self.db.execute(delete_stmt)

        deleted_id = result.scalar_one_or_none()
        return deleted_id is not None
