import logging
import uuid
from sqlalchemy import select, insert, update, func
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.balances import user_cash_balances_table
from app.db.models.orders import orders_table  # Для подсчета активов
from app.schemas.balance import BalanceResponse, AssetBalance
from app.schemas.order import OrderStatus, Direction  # Для фильтрации ордеров

logger = logging.getLogger(__name__)


class BalanceService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def _ensure_cash_balance_record(self, user_id: uuid.UUID) -> None:
        """Вспомогательная функция для создания записи баланса, если ее нет."""
        select_stmt = select(user_cash_balances_table.c.id).where(
            user_cash_balances_table.c.user_id == user_id
        )
        exists = await self.db.execute(select_stmt)
        if not exists.scalar_one_or_none():
            try:
                # Это нужно делать в рамках транзакции, если вызывается извне
                # или если deposit_to_balance не использует begin()
                insert_stmt = insert(user_cash_balances_table).values(user_id=user_id, amount=0)
                await self.db.execute(insert_stmt)
                logger.info(f"Created initial cash balance record for user {user_id}")
            except Exception as e:  # Обработка race condition, если запись создается параллельно
                logger.warning(
                    f"Could not create initial balance record for user {user_id}, possibly already exists: {e}")
                # Можно перепроверить, но обычно ошибка IntegrityError скажет об этом

    async def get_user_balance(self, user_id: uuid.UUID) -> BalanceResponse:
        logger.debug(f"Fetching balance for user {user_id}")

        # 1. Убедиться, что запись о денежном балансе существует (и создать, если нет)
        #   Это важно, чтобы total_balance всегда возвращался, даже если 0.
        #   Делаем это вне основной транзакции get_user_balance, так как это чтение.
        #   Если бы была нужна атомарность с другими операциями, то в одной транзакции.
        #   Для простоты, если deposit_to_balance отвечает за создание,
        #   то здесь можно просто ожидать 0, если записи нет.
        #   Но для консистентности total_balance, лучше обеспечить запись.

        # Вариант 1: Создавать запись при первом запросе баланса, если нет
        # await self._ensure_cash_balance_record(user_id)

        # Вариант 2 (предпочтительнее для get): Просто читать, что есть. deposit создаст запись.
        cash_balance_stmt = select(user_cash_balances_table.c.amount).where(
            user_cash_balances_table.c.user_id == user_id
        )
        cash_result = await self.db.execute(cash_balance_stmt)
        cash_amount_scalar = cash_result.scalar_one_or_none()
        total_cash = cash_amount_scalar if cash_amount_scalar is not None else 0  # total_balance из OpenAPI

        # 2. Подсчитать активы ( поле assets из OpenAPI)
        asset_balances: list[AssetBalance] = []

        # Покупки (учитываем только полностью или частично исполненные)
        buy_stmt = (
            select(orders_table.c.ticker, func.sum(orders_table.c.filled_qty).label("total_bought"))
            .where(
                orders_table.c.user_id == user_id,
                orders_table.c.direction == Direction.BUY,
                orders_table.c.status.in_([OrderStatus.EXECUTED, OrderStatus.PARTIALLY_EXECUTED]),
                orders_table.c.filled_qty > 0,
            )
            .group_by(orders_table.c.ticker)
        )
        buy_results = await self.db.execute(buy_stmt)
        bought_assets = {row.ticker: row.total_bought for row in buy_results.mappings().all()}

        # Продажи (учитываем только полностью или частично исполненные)
        sell_stmt = (
            select(orders_table.c.ticker, func.sum(orders_table.c.filled_qty).label("total_sold"))
            .where(
                orders_table.c.user_id == user_id,
                orders_table.c.direction == Direction.SELL,
                orders_table.c.status.in_([OrderStatus.EXECUTED, OrderStatus.PARTIALLY_EXECUTED]),
                orders_table.c.filled_qty > 0,
            )
            .group_by(orders_table.c.ticker)
        )
        sell_results = await self.db.execute(sell_stmt)
        sold_assets = {row.ticker: row.total_sold for row in sell_results.mappings().all()}

        all_involved_tickers = set(bought_assets.keys()) | set(sold_assets.keys())
        for ticker_value in all_involved_tickers:
            current_amount = bought_assets.get(ticker_value, 0) - sold_assets.get(ticker_value, 0)
            if current_amount > 0:  # Показываем только активы с положительным количеством
                asset_balances.append(AssetBalance(ticker=ticker_value, amount=current_amount))

        logger.info(f"Balance for user {user_id}: cash={total_cash}, assets_count={len(asset_balances)}")
        return BalanceResponse(total_balance=total_cash, assets=asset_balances)

    async def deposit_to_balance(self, user_id: uuid.UUID, deposit_amount: int) -> BalanceResponse:
        if deposit_amount <= 0:  # Дополнительная серверная валидация, хотя Pydantic уже проверил gt=0
            logger.warning(f"Attempt to deposit non-positive amount {deposit_amount} by user {user_id}")
            raise ValueError("Deposit amount must be positive.")  # Это превратится в 500, если не поймать в роутере
            # или можно сразу кидать HTTPException

        logger.info(f"Processing deposit of {deposit_amount} for user {user_id}")
        async with self.db.begin():  # Начать транзакцию для атомарности
            # Проверяем, есть ли уже запись для пользователя
            select_stmt = select(user_cash_balances_table.c.id).where(
                user_cash_balances_table.c.user_id == user_id
            )
            existing_user_balance_record = await self.db.execute(select_stmt)

            if existing_user_balance_record.scalar_one_or_none():
                # Обновить баланс
                update_stmt = (
                    update(user_cash_balances_table)
                    .where(user_cash_balances_table.c.user_id == user_id)
                    .values(amount=user_cash_balances_table.c.amount + deposit_amount)
                    .returning(user_cash_balances_table.c.amount)  # Для логгирования нового баланса
                )
                res = await self.db.execute(update_stmt)
                new_bal = res.scalar_one()
                logger.info(f"Updated balance for user {user_id} to {new_bal} after deposit.")
            else:
                # Создать новую запись баланса
                # Это более явный контроль, чем UPSERT для SQLite, который сложнее с SQLAlchemy Core.
                # Для PostgreSQL можно было бы использовать on_conflict_do_update.
                insert_stmt = insert(user_cash_balances_table).values(
                    user_id=user_id, amount=deposit_amount
                ).returning(user_cash_balances_table.c.amount)
                res = await self.db.execute(insert_stmt)
                new_bal = res.scalar_one()
                logger.info(f"Created initial balance for user {user_id} with {new_bal} during deposit.")

            # self.db.commit() не нужен с `async with self.db.begin()`

        # Вернуть обновленный полный баланс (включая активы)
        return await self.get_user_balance(user_id)