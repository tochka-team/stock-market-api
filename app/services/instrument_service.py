from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.instruments import instruments_table
from app.schemas.instrument import Instrument


async def get_all_instruments(db: AsyncConnection) -> List[Instrument]:
    """
    Получает список всех торговых инструментов из базы данных.
    """
    select_stmt = select(instruments_table)

    result = await db.execute(select_stmt)
    instruments_rows = result.fetchall()

    instruments = [Instrument.model_validate(row) for row in instruments_rows]

    return instruments
