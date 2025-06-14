from typing import List

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.transactions import transactions_table
from app.schemas.transaction import Transaction


class TransactionService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def get_transactions_by_ticker(
        self,
        ticker: str,
        limit: int = 20,
    ) -> List[Transaction]:
        """
        Получает историю сделок (транзакций) для указанного тикера.
        Возвращает список объектов Transaction, отсортированных по времени (новые первыми).
        """
        stmt = (
            select(
                transactions_table.c.ticker,
                transactions_table.c.amount,
                transactions_table.c.price,
                transactions_table.c.timestamp,
            )
            .where(transactions_table.c.ticker == ticker)
            .order_by(desc(transactions_table.c.timestamp))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        transaction_rows = result.mappings().all()

        transactions = [Transaction.model_validate(row) for row in transaction_rows]

        return transactions
