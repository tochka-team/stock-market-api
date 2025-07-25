from sqlalchemy import UUID as GenericUUID
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)

from app.db.metadata import metadata

from .instruments import instruments_table
from .users import users_table

balances_table = Table(
    "balances",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "user_id",
        GenericUUID(as_uuid=True),
        ForeignKey(users_table.c.id, name="fk_balances_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "ticker",
        String(20),
        ForeignKey(
            instruments_table.c.ticker,
            name="fk_balances_instrument_ticker",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="Тикер актива или валюты (e.g., 'AAPL', 'RUB')",
    ),
    Column(
        "amount",
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Текущее количество актива или денежных средств на балансе",
    ),
    Column(
        "locked_amount",
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Количество актива или денежных средств, заблокированное в активных ордерах",
    ),
    UniqueConstraint("user_id", "ticker", name="uq_user_ticker_balance"),
    Column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)
