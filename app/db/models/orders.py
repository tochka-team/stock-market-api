# app/db/models/orders.py
import uuid
from sqlalchemy import Table, Column, String, Integer, DateTime, func, Index, Enum as SqlEnum
from sqlalchemy import UUID as GenericUUID

from app.db.metadata import metadata
from app.schemas.order import OrderStatus, OrderDirection
import enum

class DBOrderStatus(str, enum.Enum):
    NEW = "NEW"
    EXECUTED = "EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    CANCELLED = "CANCELLED"

class DBOrderDirection(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


orders_table = Table(
    "orders",
    metadata,
    Column(
        "id",
        GenericUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ),
    Column("user_id", PG_UUID(as_uuid=True), nullable=False, index=True),
    Column("ticker", String(20), nullable=False),
    Column("direction", SqlEnum(DBOrderDirection, name="order_direction_enum", create_type=True), nullable=False),
    Column("qty", Integer, nullable=False),
    Column("price", Integer, nullable=True),
    Column("status", SqlEnum(DBOrderStatus, name="order_status_enum", create_type=True), nullable=False, default=DBOrderStatus.NEW),
    Column("filled_qty", Integer, nullable=False, default=0, server_default="0"),
    Column(
        "timestamp",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
    Index(
        "ix_orders_active_for_matching",
        "ticker",
        "direction",
        "status",
        "price",
    ),
)