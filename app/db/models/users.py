from sqlalchemy import Table, Column, String
import enum
import uuid

from app.db.metadata import metadata

class UserRole(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"

users_table = Table(
    "users",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("role", String(10), nullable=False, default=UserRole.USER.value),
    Column("api_key", String(100), nullable=False, unique=True, index=True)
)