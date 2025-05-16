from sqlalchemy import UUID as GenericUUID
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Table, func

from app.db.metadata import metadata

user_cash_balances_table = Table(
    "user_cash_balances",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "user_id",
        GenericUUID(as_uuid=True),
        ForeignKey(
            "users.id", name="fk_user_cash_balances_user_id", ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
        index=True,
    ),
    Column(
        "amount",
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Сумма в копейках. Соответствует total_balance из BalanceResponse",
    ),
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
