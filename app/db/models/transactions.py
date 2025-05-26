import uuid

from sqlalchemy import UUID as GenericUUID
from sqlalchemy import Column, DateTime, Integer, String, Table, func, ForeignKey

from app.db.metadata import metadata
from .orders import orders_table
from .users import users_table


transactions_table = Table(
    "transactions",
    metadata,
    Column(
        "id",
        GenericUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ),
    Column("ticker", String(20), nullable=False, index=True),
    Column("amount", Integer, nullable=False),
    Column("price", Integer, nullable=False),
    Column(
        "timestamp",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    ),
    Column(
        "buy_order_id",
        GenericUUID(as_uuid=True), 
        ForeignKey(orders_table.c.id, name="fk_transactions_buy_order_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    ),
    Column(
        "sell_order_id",
        GenericUUID(as_uuid=True),
        ForeignKey(orders_table.c.id, name="fk_transactions_sell_order_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    ),
    Column(
        "buyer_user_id",
        GenericUUID(as_uuid=True),
        ForeignKey(users_table.c.id, name="fk_transactions_buyer_user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    ),
    Column(
        "seller_user_id",
        GenericUUID(as_uuid=True),
        ForeignKey(users_table.c.id, name="fk_transactions_seller_user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    ),
)
