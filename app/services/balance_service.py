import logging
import uuid
from typing import Dict

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.balances import balances_table

logger = logging.getLogger(__name__)


class BalanceService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def get_user_balance(self, user_id: uuid.UUID) -> Dict[str, int]:
        """
        Получает все балансы пользователя (денежные и активы) из таблицы `balances`.
        Возвращает словарь, где ключ - тикер, значение - количество.
        Например: {"RUB": 10000, "AAPL": 5, "MEMCOIN": 1000}
        """
        logger.debug(f"Fetching all balances for user_id: {user_id}")

        stmt = select(balances_table.c.ticker, balances_table.c.amount).where(
            balances_table.c.user_id == user_id
        )

        result = await self.db.execute(stmt)
        user_balances_rows = result.mappings().all()

        balances_dict: Dict[str, int] = {}
        for row in user_balances_rows:
            balances_dict[row["ticker"]] = row["amount"]
        if "RUB" not in balances_dict:
            balances_dict["RUB"] = 0

        logger.info(f"Fetched balances for user {user_id}: {balances_dict}")
        return balances_dict

    async def admin_update_or_create_balance(
        self,
        user_id: uuid.UUID,
        ticker: str,
        change_amount: int,
        operation: str = "deposit",
    ) -> bool:
        """
        Административная функция для пополнения или списания баланса.
        change_amount: положительное для пополнения, отрицательное для списания.
        operation: "deposit" или "withdraw" для логирования и проверки.
        """
        if operation == "deposit" and change_amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        if operation == "withdraw" and change_amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")

        current_balance_stmt = select(balances_table.c.amount).where(
            (balances_table.c.user_id == user_id)
            & (balances_table.c.ticker == ticker)
        )
        current_balance_res = await self.db.execute(current_balance_stmt)
        current_amount = current_balance_res.scalar_one_or_none()

        if current_amount is not None:
            new_amount = current_amount
            if operation == "deposit":
                new_amount += change_amount
            elif operation == "withdraw":
                if current_amount < change_amount:
                    logger.warning(
                        f"Insufficient balance for withdrawal: user {user_id}, ticker {ticker}, wants {change_amount}, has {current_amount}"
                    )
                    raise ValueError(
                        f"Insufficient balance for ticker {ticker} to withdraw {change_amount}."
                    )
                new_amount -= change_amount

            update_stmt = (
                update(balances_table)
                .where(
                    (balances_table.c.user_id == user_id)
                    & (balances_table.c.ticker == ticker)
                )
                .values(amount=new_amount)
            )
            await self.db.execute(update_stmt)
            logger.info(
                f"Admin {operation}: Updated balance for user {user_id}, ticker {ticker} to {new_amount}"
            )
        else:
            if operation == "withdraw":
                logger.warning(
                    f"Admin withdrawal attempt from non-existent balance: user {user_id}, ticker {ticker}"
                )
                raise ValueError(
                    f"Cannot withdraw from non-existent balance for ticker {ticker}."
                )

            insert_stmt = insert(balances_table).values(
                user_id=user_id,
                ticker=ticker,
                amount=change_amount,
                locked_amount=0,
            )
            await self.db.execute(insert_stmt)
            logger.info(
                f"Admin {operation}: Created balance for user {user_id}, ticker {ticker} with amount {change_amount}"
            )

        return True
