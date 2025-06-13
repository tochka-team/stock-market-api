import logging
import uuid
from typing import Dict, Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.models.balances import balances_table

logger = logging.getLogger(__name__)


class BalanceService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def get_balance(self, user_id: uuid.UUID, ticker: str) -> Dict[str, int]:
        """
        Получить баланс пользователя для указанного тикера.
        """
        logger.debug(f"Fetching balance for user_id: {user_id}, ticker: {ticker}")
        
        stmt = select(balances_table).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        )
        result = await self.db.execute(stmt)
        balance = result.fetchone()
        
        if balance:
            return {"amount": balance.amount, "locked_amount": balance.locked_amount}
        else:
            logger.info(f"No balance record for user {user_id}, ticker {ticker}. Returning zero balances.")
            return {"amount": 0, "locked_amount": 0}

    async def get_all_balances(self, user_id: uuid.UUID) -> Dict[str, int]:
        """
        Получить все балансы пользователя.
        """
        logger.debug(f"Fetching all balances for user_id: {user_id}")

        stmt = select(balances_table).where(balances_table.c.user_id == user_id)
        result = await self.db.execute(stmt)
        balances = result.fetchall()
        
        balance_dict = {}
        for balance in balances:
            # Возвращаем только available балансы (amount - locked_amount)
            available_amount = balance.amount - balance.locked_amount
            if available_amount > 0:  # Показываем только положительные балансы
                balance_dict[balance.ticker] = available_amount
        
        logger.info(f"Fetched balances for user {user_id}: {balance_dict}")
        return balance_dict

    async def admin_deposit(self, user_id: uuid.UUID, ticker: str, amount: int):
        """
        Административное пополнение баланса пользователя.
        """
        logger.info(f"Admin deposit: user_id={user_id}, ticker={ticker}, amount={amount}")
        
        # ATOMIC: Используем SELECT FOR UPDATE для блокировки записи
        select_stmt = select(balances_table).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        ).with_for_update()
        
        result = await self.db.execute(select_stmt)
        existing_balance = result.fetchone()
        
        if existing_balance:
            # Обновляем существующий баланс
            update_stmt = update(balances_table).where(
                and_(
                    balances_table.c.user_id == user_id,
                    balances_table.c.ticker == ticker
                )
            ).values(amount=existing_balance.amount + amount)
            
            await self.db.execute(update_stmt)
            logger.info(f"Admin deposit: Updated balance for user {user_id}, ticker {ticker}. New amount: {existing_balance.amount + amount}")
        else:
            # Создаем новую запись
            insert_stmt = balances_table.insert().values(
                user_id=user_id,
                ticker=ticker,
                amount=amount,
                locked_amount=0
            )
            await self.db.execute(insert_stmt)
            logger.info(f"Admin deposit: Created balance for user {user_id}, ticker {ticker} with amount {amount}")

    async def block_funds(self, user_id: uuid.UUID, ticker: str, amount: int) -> bool:
        """
        Заблокировать средства пользователя для ордера.
        ATOMIC OPERATION с проверками и retry логикой.
        """
        logger.info(f"BLOCK_FUNDS: Attempting to block {amount} of {ticker} for user {user_id}")
        
        max_retries = 3
        base_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                return await self._block_funds_atomic(user_id, ticker, amount)
            except DBAPIError as e:
                if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                    import asyncio
                    delay = base_delay * (2 ** attempt)  # Экспоненциальная задержка
                    logger.warning(f"Deadlock detected in block_funds, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Failed to block funds after {max_retries} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error in block_funds: {e}")
                raise

    async def _block_funds_atomic(self, user_id: uuid.UUID, ticker: str, amount: int) -> bool:
        """
        Атомарная блокировка средств.
        """
        # ATOMIC: SELECT FOR UPDATE для предотвращения race conditions
        select_stmt = select(balances_table).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        ).with_for_update()
        
        result = await self.db.execute(select_stmt)
        balance = result.fetchone()
        
        if not balance:
            # Создаем запись с нулевыми балансами если её нет
            logger.info(f"No balance record for user {user_id}, ticker {ticker}. Creating one with 0 amounts.")
            insert_stmt = balances_table.insert().values(
                user_id=user_id,
                ticker=ticker,
                amount=0,
                locked_amount=0
            )
            await self.db.execute(insert_stmt)
            logger.info(f"Created balance record for user {user_id}, ticker {ticker}: {'amount': 0, 'locked_amount': 0}")
            
            # Недостаточно средств для блокировки
            logger.error(f"Insufficient available balance for user {user_id}, ticker {ticker} to block {amount}. Available: 0, Required: {amount}")
            return False
        
        # Вычисляем доступные средства
        available_amount = balance.amount - balance.locked_amount
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: не допускаем отрицательных значений
        if balance.locked_amount < 0:
            logger.error(f"CRITICAL: Negative locked balance detected! User {user_id}, ticker {ticker}, locked: {balance.locked_amount}")
            # Исправляем отрицательный locked balance
            fix_stmt = update(balances_table).where(
                and_(
                    balances_table.c.user_id == user_id,
                    balances_table.c.ticker == ticker
                )
            ).values(locked_amount=0)
            await self.db.execute(fix_stmt)
            logger.info(f"Fixed negative locked balance for user {user_id}, ticker {ticker}")
            available_amount = balance.amount
        
        logger.info(f"BLOCK_FUNDS: User {user_id}, ticker {ticker} - Available: {available_amount}, Locked: {balance.locked_amount}, Trying to block: {amount}")
        
        # Проверяем достаточность средств
        if available_amount < amount:
            logger.error(f"Insufficient available balance for user {user_id}, ticker {ticker} to block {amount}. Available: {available_amount}, Required: {amount}")
            return False
        
        # ATOMIC UPDATE: блокируем средства
        new_locked_amount = balance.locked_amount + amount
        new_available_amount = balance.amount - new_locked_amount
        
        # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: не допускаем отрицательных available
        if new_available_amount < 0:
            logger.error(f"Would create negative available balance! User {user_id}, ticker {ticker}, amount: {balance.amount}, new_locked: {new_locked_amount}")
            return False

        update_stmt = update(balances_table).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        ).values(locked_amount=new_locked_amount)
        
        await self.db.execute(update_stmt)
        
        logger.info(f"Successfully blocked {amount} of {ticker} for user {user_id}. New available: {new_available_amount}, New locked: {new_locked_amount}")
        return True

    async def unblock_funds(self, user_id: uuid.UUID, ticker: str, amount: int):
        """
        Разблокировать средства пользователя при отмене ордера.
        ATOMIC OPERATION с проверками и retry логикой.
        """
        logger.info(f"Attempting to unblock {amount} of {ticker} for user {user_id}")
        
        max_retries = 3
        base_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                await self._unblock_funds_atomic(user_id, ticker, amount)
                return  # Успешно выполнено
            except DBAPIError as e:
                if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                    import asyncio
                    delay = base_delay * (2 ** attempt)  # Экспоненциальная задержка
                    logger.warning(f"Deadlock detected in unblock_funds, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Failed to unblock funds after {max_retries} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error in unblock_funds: {e}")
                raise

    async def _unblock_funds_atomic(self, user_id: uuid.UUID, ticker: str, amount: int):
        """
        Атомарная разблокировка средств.
        """
        # ATOMIC: SELECT FOR UPDATE
        select_stmt = select(balances_table).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        ).with_for_update()
        
        result = await self.db.execute(select_stmt)
        balance = result.fetchone()
        
        if not balance:
            logger.error(f"No balance record found for user {user_id}, ticker {ticker} during unblock")
            return
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: не допускаем отрицательных locked
        new_locked_amount = max(0, balance.locked_amount - amount)  # Не позволяем locked стать отрицательным
        new_available_amount = balance.amount - new_locked_amount
        
        if balance.locked_amount < amount:
            logger.warning(f"Trying to unblock more than locked! User {user_id}, ticker {ticker}, locked: {balance.locked_amount}, trying to unblock: {amount}")
        
        # ATOMIC UPDATE
        update_stmt = update(balances_table).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        ).values(locked_amount=new_locked_amount)
        
        await self.db.execute(update_stmt)
        
        logger.info(f"Unblocked {amount} of {ticker} for user {user_id}. New available: {new_available_amount}, new locked: {new_locked_amount}")

    async def execute_trade_balances(
        self,
        buyer_id: uuid.UUID,
        seller_id: uuid.UUID,
        ticker: str,
        trade_qty: int,
        trade_price: int,
    ):
        """
        Основной метод для обновления балансов при исполнении сделки.
        Включает retry логику для обработки deadlocks и ATOMIC operations.
        """
        logger.info(
            f"Executing trade balances: Buyer {buyer_id}, Seller {seller_id}, "
            f"{trade_qty} of {ticker} @ {trade_price} (Total sum: {trade_qty * trade_price} RUB)"
        )
        
        max_retries = 3
        base_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                # ATOMIC OPERATION: Блокируем ВСЕ балансы участников сделки
                await self._execute_trade_atomic(buyer_id, seller_id, ticker, trade_qty, trade_price)
                return  # Успешно выполнено
                
            except DBAPIError as e:
                if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                    import asyncio
                    delay = base_delay * (2 ** attempt)  # Экспоненциальная задержка
                    logger.warning(f"Deadlock detected, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Failed to execute trade balances after {max_retries} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error in execute_trade_balances: {e}")
                raise

    async def _execute_trade_atomic(
        self,
        buyer_id: uuid.UUID,
        seller_id: uuid.UUID,
        ticker: str,
        trade_qty: int,
        trade_price: int,
    ):
        """
        Атомарное исполнение сделки с проверками.
        ВАЖНО: Блокируем балансы в строго упорядоченной последовательности для предотвращения deadlocks.
        """
        logger.debug(f"TRADE_DEBUG: Attempt for trade buyer={buyer_id} seller={seller_id}")
        
        # КРИТИЧЕСКИ ВАЖНО: Создаем список ВСЕХ balance records участвующих в сделке
        # и сортируем их по (user_id, ticker) для предотвращения deadlocks
        balance_locks = []
        balance_locks.append((buyer_id, "RUB"))      # Покупатель платит RUB
        balance_locks.append((buyer_id, ticker))     # Покупатель получает актив
        balance_locks.append((seller_id, "RUB"))     # Продавец получает RUB
        balance_locks.append((seller_id, ticker))    # Продавец отдает актив
        
        # Убираем дубликаты и сортируем для единого порядка блокировки
        balance_locks = list(set(balance_locks))
        balance_locks.sort()  # Сортируем по (user_id, ticker)
        
        logger.debug(f"TRADE_DEBUG: Locking balances in order: {balance_locks}")
        
        # Блокируем ВСЕ балансы в едином порядке
        locked_balances = {}
        for user_id, lock_ticker in balance_locks:
            stmt = select(balances_table).where(
                and_(balances_table.c.user_id == user_id, balances_table.c.ticker == lock_ticker)
            ).with_for_update()
            
            result = await self.db.execute(stmt)
            balance = result.fetchone()
            
            # Создаем баланс если не существует
            if not balance:
                await self._create_balance_if_not_exists(user_id, lock_ticker)
                # Повторно блокируем после создания
                result = await self.db.execute(stmt)
                balance = result.fetchone()
            
            locked_balances[(user_id, lock_ticker)] = balance
        
        # Получаем нужные балансы
        buyer_rub_balance = locked_balances[(buyer_id, "RUB")]
        buyer_ticker_balance = locked_balances.get((buyer_id, ticker))
        seller_rub_balance = locked_balances.get((seller_id, "RUB"))
        seller_ticker_balance = locked_balances[(seller_id, ticker)]
        
        # Логируем состояние ДО сделки
        required_rub = trade_qty * trade_price
        logger.debug(
            f"TRADE_DEBUG: Pre-trade balances - "
            f"Buyer {buyer_id} RUB: available={buyer_rub_balance.amount - buyer_rub_balance.locked_amount}, locked={buyer_rub_balance.locked_amount}. "
            f"Seller {seller_id} {ticker}: available={seller_ticker_balance.amount - seller_ticker_balance.locked_amount}, locked={seller_ticker_balance.locked_amount}. "
            f"Required: buyer_locked_rub >= {required_rub}, seller_locked_{ticker} >= {trade_qty}"
        )
        
        # КРИТИЧЕСКИЕ ПРОВЕРКИ
        if buyer_rub_balance.locked_amount < required_rub:
            raise Exception(f"Buyer {buyer_id} insufficient locked RUB for trade. Required: {required_rub}, Locked: {buyer_rub_balance.locked_amount}, Available: {buyer_rub_balance.amount - buyer_rub_balance.locked_amount}.")
            
        if seller_ticker_balance.locked_amount < trade_qty:
            raise Exception(f"Seller {seller_id} insufficient locked {ticker} for trade. Required: {trade_qty}, Locked: {seller_ticker_balance.locked_amount}, Available: {seller_ticker_balance.amount - seller_ticker_balance.locked_amount}.")
        
        # АТОМАРНЫЕ ОБНОВЛЕНИЯ
        total_rub_cost = trade_qty * trade_price
        
        # 1. Уменьшаем заблокированные RUB у покупателя
        await self._update_balance(buyer_id, "RUB", "locked_decrease", total_rub_cost)
        
        # 2. Увеличиваем количество активов у покупателя
        await self._update_balance(buyer_id, ticker, "amount_increase", trade_qty)
        
        # 3. Уменьшаем заблокированные активы у продавца
        await self._update_balance(seller_id, ticker, "locked_decrease", trade_qty)
        
        # 4. Увеличиваем RUB у продавца
        await self._update_balance(seller_id, "RUB", "amount_increase", total_rub_cost)
        
        logger.info(f"Successfully executed trade of {ticker}, qty {trade_qty}, price {trade_price} between buyer {buyer_id} and seller {seller_id}")

    async def _create_balance_if_not_exists(self, user_id: uuid.UUID, ticker: str):
        """
        Создать запись баланса если она не существует.
        """
        logger.debug(f"Creating balance record if not exists for user {user_id}, ticker {ticker}")
        
        # Проверяем существование записи
        select_stmt = select(balances_table).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        )
        result = await self.db.execute(select_stmt)
        existing = result.fetchone()
        
        if not existing:
            # Создаем новую запись с нулевыми балансами
            insert_stmt = balances_table.insert().values(
                user_id=user_id,
                ticker=ticker,
                amount=0,
                locked_amount=0
            )
            await self.db.execute(insert_stmt)
            logger.info(f"Created balance record for user {user_id}, ticker {ticker}")

    async def _get_or_create_balance_record(self, user_id: uuid.UUID, ticker: str, create_if_not_exists: bool = True) -> Optional[Dict[str, int]]:
        """
        Получить запись баланса или создать если не существует.
        """
        logger.debug(f"Getting or creating balance record for user {user_id}, ticker {ticker}")
        
        stmt = select(balances_table).where(
            and_(
                balances_table.c.user_id == user_id,
                balances_table.c.ticker == ticker
            )
        )
        result = await self.db.execute(stmt)
        balance = result.fetchone()
        
        if balance:
            return {"amount": balance.amount, "locked_amount": balance.locked_amount}
        elif create_if_not_exists:
            # Создаем новую запись
            insert_stmt = balances_table.insert().values(
                user_id=user_id,
                ticker=ticker,
                amount=0,
                locked_amount=0
            )
            await self.db.execute(insert_stmt)
            logger.info(f"Created balance record for user {user_id}, ticker {ticker}")
            return {"amount": 0, "locked_amount": 0}
        else:
            return None

    async def _update_balance(self, user_id: uuid.UUID, ticker: str, operation: str, amount: int):
        """
        Атомарное обновление баланса с проверками.
        """
        if operation == "amount_increase":
            stmt = update(balances_table).where(
                and_(balances_table.c.user_id == user_id, balances_table.c.ticker == ticker)
            ).values(amount=balances_table.c.amount + amount)
        elif operation == "amount_decrease":
            stmt = update(balances_table).where(
                and_(balances_table.c.user_id == user_id, balances_table.c.ticker == ticker)
            ).values(amount=balances_table.c.amount - amount)
        elif operation == "locked_increase":
            stmt = update(balances_table).where(
                and_(balances_table.c.user_id == user_id, balances_table.c.ticker == ticker)
            ).values(locked_amount=balances_table.c.locked_amount + amount)
        elif operation == "locked_decrease":
            # ВАЖНО: Не позволяем locked стать отрицательным
            stmt = update(balances_table).where(
                and_(balances_table.c.user_id == user_id, balances_table.c.ticker == ticker)
            ).values(locked_amount=balances_table.c.locked_amount - amount)
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        await self.db.execute(stmt)
        logger.debug(f"Updated balance for user {user_id}, ticker {ticker}, operation {operation}, amount {amount}")
