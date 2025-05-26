import uuid

from sqlalchemy import UUID as GenericUUID
from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Table, func

from app.db.metadata import metadata
from app.schemas.order import Direction, OrderStatus

from .users import users_table
from .instruments import instruments_table

orders_table = Table(
    "orders",
    metadata,
    Column(
        "id",
        GenericUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ),
    Column(
        "user_id",
        GenericUUID(as_uuid=True),
        ForeignKey(users_table.c.id, name="fk_orders_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "ticker",
        String(20),
        ForeignKey(instruments_table.c.ticker, name="fk_orders_instrument_ticker", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "direction",
        SqlEnum(Direction, name="order_direction_enum", create_type=False),
        nullable=False,
    ),
    Column("qty", Integer, nullable=False),
    Column("price", Integer, nullable=True),
    Column(
        "status",
        SqlEnum(OrderStatus, name="order_status_enum", create_type=False),
        nullable=False,
        default=OrderStatus.NEW,
    ),
    Column("filled_qty", Integer, nullable=False, default=0, server_default="0"),
    Column(
        "timestamp",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
    # Составной индекс для matching engine и стакана заявок
    # Важно: порядок колонок в индексе имеет значение!
    # Обычно: тикер, статус (чтобы отфильтровать неактивные), направление, цена (для сортировки).
    Index(
        "ix_orders_active_for_matching",
        "ticker",
        "status",
        "direction",
        "price",
    ),
)
