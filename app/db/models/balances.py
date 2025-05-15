# app/db/models/balances.py
import uuid
from sqlalchemy import Column, Integer, Table, ForeignKey, DateTime, func
from sqlalchemy import UUID as GenericUUID # Используется в других моделях, поддержим консистентность

from app.db.metadata import metadata

# Таблица для хранения денежного баланса пользователей
user_cash_balances_table = Table(
    "user_cash_balances",
    metadata,
    # Можно использовать автоинкрементный ID или UUID, если user_id уже UUID,
    # то отдельный PK может быть Integer для простоты.
    # Если user_id будет PK, то он должен быть уникальным.
    # В данном случае, user_id будет внешним ключом и уникальным индексом.
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", GenericUUID(as_uuid=True), ForeignKey("users.id", name="fk_user_cash_balances_user_id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
    Column("amount", Integer, nullable=False, default=0, server_default="0", comment="Сумма в копейках. Соответствует total_balance из BalanceResponse"),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
)