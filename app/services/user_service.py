from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.users import users_table
from app.schemas.user import User

class UserService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def delete_user(self, user_id: UUID) -> bool:
        """Удаляет пользователя и возвращает True если удаление успешно"""
        delete_stmt = (
            delete(users_table)
            .where(users_table.c.id == user_id)
            .returning(users_table.c.id)
        )
        result = await self.db.execute(delete_stmt)
        return bool(result.scalar_one_or_none())