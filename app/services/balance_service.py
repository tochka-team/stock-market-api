import logging
import uuid
from typing import Dict, Optional

from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.models.balances import balances_table
from app.db.models.orders import orders_table
from app.schemas.order import Direction, OrderStatus

logger = logging.getLogger(__name__)


class BalanceService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def get_balance(self, user_id: uuid.UUID, ticker: str) -> int:
        """
        Получить баланс пользователя для указанного тикера.
        Возвращает только amount.
        """
        stmt = select(balances_table.c.amount).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        )
        result = await self.db.execute(stmt)
        balance = result.scalar()
        
        return balance if balance is not None else 0

    async def get_all_balances(self, user_id: uuid.UUID) -> Dict[str, int]:
        """
        Получить все балансы пользователя.
        Возвращает только положительные балансы.
        """
        stmt = select(balances_table.c.ticker, balances_table.c.amount).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.amount > 0
            )
        )
        result = await self.db.execute(stmt)
        balances = result.fetchall()
        
        return {row.ticker: row.amount for row in balances}

    async def admin_deposit(self, user_id: uuid.UUID, ticker: str, amount: int):
        """
        Административное пополнение баланса пользователя.
        """
        logger.info(f"Admin deposit: user_id={user_id}, ticker={ticker}, amount={amount}")
        
        await self._ensure_balance_exists(user_id, ticker)
        
        update_stmt = update(balances_table).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        ).values(amount=balances_table.c.amount + amount)
        
        await self.db.execute(update_stmt)
        logger.info(f"Admin deposit completed: {amount} {ticker} to user {user_id}")

    async def execute_trade_atomic(
        self,
        buyer_id: uuid.UUID,
        seller_id: uuid.UUID,
        ticker: str,
        trade_qty: int,
        trade_price: int,
    ):
        """
        Все проверки и операции в одной транзакции с блокировками.
        """
        total_rub = trade_qty * trade_price
        
        logger.info(f"Executing atomic trade: buyer={buyer_id}, seller={seller_id}, ticker={ticker}, qty={trade_qty}, price={trade_price}")
        
        await self._ensure_balance_exists(buyer_id, "RUB")
        await self._ensure_balance_exists(buyer_id, ticker)
        await self._ensure_balance_exists(seller_id, "RUB")
        await self._ensure_balance_exists(seller_id, ticker)
        
        buyer_rub_stmt = select(balances_table.c.amount).where(
            and_(balances_table.c.user_id == buyer_id, balances_table.c.ticker == "RUB")
        ).with_for_update()
        
        buyer_ticker_stmt = select(balances_table.c.amount).where(
            and_(balances_table.c.user_id == buyer_id, balances_table.c.ticker == ticker)
        ).with_for_update()
        
        seller_rub_stmt = select(balances_table.c.amount).where(
            and_(balances_table.c.user_id == seller_id, balances_table.c.ticker == "RUB")
        ).with_for_update()
        
        seller_ticker_stmt = select(balances_table.c.amount).where(
            and_(balances_table.c.user_id == seller_id, balances_table.c.ticker == ticker)
        ).with_for_update()
        
        buyer_rub_balance = (await self.db.execute(buyer_rub_stmt)).scalar() or 0
        buyer_ticker_balance = (await self.db.execute(buyer_ticker_stmt)).scalar() or 0
        seller_rub_balance = (await self.db.execute(seller_rub_stmt)).scalar() or 0
        seller_ticker_balance = (await self.db.execute(seller_ticker_stmt)).scalar() or 0
        
        if buyer_rub_balance < total_rub:
            raise ValueError(f"Buyer {buyer_id} has insufficient RUB: {buyer_rub_balance} < {total_rub}")
        
        if seller_ticker_balance < trade_qty:
            raise ValueError(f"Seller {seller_id} has insufficient {ticker}: {seller_ticker_balance} < {trade_qty}")
        
        await self.db.execute(
            update(balances_table).where(
                and_(balances_table.c.user_id == buyer_id, balances_table.c.ticker == "RUB")
            ).values(amount=buyer_rub_balance - total_rub)
        )
        
        await self.db.execute(
            update(balances_table).where(
                and_(balances_table.c.user_id == buyer_id, balances_table.c.ticker == ticker)
            ).values(amount=buyer_ticker_balance + trade_qty)
        )
        
        await self.db.execute(
            update(balances_table).where(
                and_(balances_table.c.user_id == seller_id, balances_table.c.ticker == "RUB")
            ).values(amount=seller_rub_balance + total_rub)
        )
        
        await self.db.execute(
            update(balances_table).where(
                and_(balances_table.c.user_id == seller_id, balances_table.c.ticker == ticker)
            ).values(amount=seller_ticker_balance - trade_qty)
        )
        
        logger.info(f"Atomic trade executed successfully: {trade_qty} {ticker} @ {trade_price} RUB")

    async def _ensure_balance_exists(self, user_id: uuid.UUID, ticker: str):
        """
        Обеспечить существование записи баланса.
        """
        check_stmt = select(func.count()).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        )
        exists = (await self.db.execute(check_stmt)).scalar() > 0
        
        if not exists:
            try:
                insert_stmt = balances_table.insert().values(
                    user_id=user_id,
                    ticker=ticker,
                    amount=0,
                    locked_amount=0  
                )
                await self.db.execute(insert_stmt)
                logger.debug(f"Created balance record: user {user_id}, ticker {ticker}")
            except IntegrityError:
                pass

    async def check_sufficient_balance(self, user_id: uuid.UUID, ticker: str, required_amount: int) -> bool:
        """Простая проверка баланса"""
        balance = await self.get_balance(user_id, ticker)
        return balance >= required_amount

    async def execute_trade_simple(self, buyer_id: uuid.UUID, seller_id: uuid.UUID, ticker: str, trade_qty: int, trade_price: int):
        """DEPRECATED: Используйте execute_trade_atomic"""
        logger.warning("execute_trade_simple is deprecated - using execute_trade_atomic")
        await self.execute_trade_atomic(buyer_id, seller_id, ticker, trade_qty, trade_price)

    async def block_funds(self, user_id: uuid.UUID, ticker: str, amount: int) -> bool:
        """DEPRECATED: Блокировка средств больше не используется"""
        logger.warning("block_funds is deprecated - no longer blocking funds")
        return True

    async def unblock_funds(self, user_id: uuid.UUID, ticker: str, amount: int):
        """DEPRECATED: Разблокировка средств больше не используется"""
        logger.warning("unblock_funds is deprecated - no longer unblocking funds")
        pass

    async def execute_trade_balances(self, buyer_id: uuid.UUID, seller_id: uuid.UUID, ticker: str, trade_qty: int, trade_price: int):
        """DEPRECATED: Используйте execute_trade_atomic"""
        logger.warning("execute_trade_balances is deprecated - using execute_trade_atomic")
        await self.execute_trade_atomic(buyer_id, seller_id, ticker, trade_qty, trade_price)
