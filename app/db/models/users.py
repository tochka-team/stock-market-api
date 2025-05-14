import uuid

from sqlalchemy import UUID as GenericUUID
from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import String, Table, func

from app.db.metadata import metadata
from app.schemas.user import UserRole

users_table = Table(
    "users",
    metadata,
    Column(
        "id",
        GenericUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ),
    Column("name", String(100), nullable=False),
    Column("role", SqlEnum(UserRole, name="user_role_enum",
           create_type=False), nullable=False, default=UserRole.USER),
    Column("api_key", String(100), nullable=False, unique=True, index=True),
    Column(
        "created_at",
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
)
