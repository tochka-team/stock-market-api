import uuid

from sqlalchemy import UUID as GenericUUID
from sqlalchemy import Column, DateTime, Integer, String, Table, func

from app.db.metadata import metadata

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
)
