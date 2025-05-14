from sqlalchemy import Column, DateTime, Integer, String, Table, func

from app.db.metadata import metadata

instruments_table = Table(
    "instruments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ticker", String(20), nullable=False, unique=True, index=True),
    Column("name", String(100), nullable=True),
    Column("description", String(255), nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)
