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

    async def _get_or_create_balance_record(
        self, user_id: uuid.UUID, ticker: str, create_if_not_exists: bool = True
    ) -> Dict:
        """Вспомогательный метод для получения или создания записи баланса."""
        select_stmt = select(balances_table.c.amount, balances_table.c.locked_amount).where(
            (balances_table.c.user_id == user_id) &
            (balances_table.c.ticker == ticker)
        )
        result = await self.db.execute(select_stmt)
        balance_record = result.mappings().one_or_none()

        if not balance_record and create_if_not_exists:
            logger.info(f"No balance record for user {user_id}, ticker {ticker}. Creating one with 0 amounts.")
            insert_stmt = insert(balances_table).values(
                user_id=user_id,
                ticker=ticker,
                amount=0,
                locked_amount=0
            ).returning(balances_table.c.amount, balances_table.c.locked_amount)
            
            created_result = await self.db.execute(insert_stmt)
            balance_record = created_result.mappings().one()
            logger.info(f"Created balance record for user {user_id}, ticker {ticker}: {balance_record}")

        elif not balance_record and not create_if_not_exists:
            return None

        return balance_record

    async def block_funds(
        self, user_id: uuid.UUID, ticker: str, amount_to_block: int
    ) -> bool:
        """
        Блокирует указанное количество средств/активов на балансе пользователя.
        Уменьшает 'amount' и увеличивает 'locked_amount'.
        Возвращает True при успехе, False или выбрасывает ValueError при неудаче.
        """
        if amount_to_block <= 0:
            raise ValueError("Amount to block must be positive.")

        balance_record = await self._get_or_create_balance_record(user_id, ticker, create_if_not_exists=False)

        if not balance_record or balance_record["amount"] < amount_to_block:
            logger.warning(
                f"Insufficient available balance for user {user_id}, ticker {ticker} "
                f"to block {amount_to_block}. Available: {balance_record.get('amount', 0) if balance_record else 0}"
            )
            return False

        new_amount = balance_record["amount"] - amount_to_block
        new_locked_amount = balance_record["locked_amount"] + amount_to_block

        update_stmt = update(balances_table).where(
            (balances_table.c.user_id == user_id) &
            (balances_table.c.ticker == ticker)
        ).values(
            amount=new_amount,
            locked_amount=new_locked_amount
        )
        await self.db.execute(update_stmt)
        logger.info(f"Blocked {amount_to_block} of {ticker} for user {user_id}. New available: {new_amount}, new locked: {new_locked_amount}")
        return True

    async def unblock_funds(
        self, user_id: uuid.UUID, ticker: str, amount_to_unblock: int
    ) -> bool:
        """
        Разблокирует указанное количество средств/активов на балансе пользователя.
        Уменьшает 'locked_amount' и увеличивает 'amount'.
        Возвращает True при успехе, False или выбрасывает ValueError при неудаче.
        """
        if amount_to_unblock <= 0:
            raise ValueError("Amount to unblock must be positive.")

        balance_record = await self._get_or_create_balance_record(user_id, ticker, create_if_not_exists=False)

        if not balance_record or balance_record["locked_amount"] < amount_to_unblock:
            logger.warning(
                f"Insufficient locked balance for user {user_id}, ticker {ticker} "
                f"to unblock {amount_to_unblock}. Locked: {balance_record.get('locked_amount', 0) if balance_record else 0}"
            )
            return False

        new_amount = balance_record["amount"] + amount_to_unblock
        new_locked_amount = balance_record["locked_amount"] - amount_to_unblock

        update_stmt = update(balances_table).where(
            (balances_table.c.user_id == user_id) &
            (balances_table.c.ticker == ticker)
        ).values(
            amount=new_amount,
            locked_amount=new_locked_amount
        )
        await self.db.execute(update_stmt)
        logger.info(f"Unblocked {amount_to_unblock} of {ticker} for user {user_id}. New available: {new_amount}, new locked: {new_locked_amount}")
        return True
