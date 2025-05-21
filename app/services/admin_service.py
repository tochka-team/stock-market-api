from uuid import UUID
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.users import users_table
from app.schemas.user import User

class AdminService:
    def __init__(self, db:AsyncConnection):
        self.db = db

    async def delete_user(self, user_id: UUID) -> bool:
        """
        Удаляет пользователя по ID.
        Возвращает True, если пользователь был удален, False — если не найден.
        """
        delete_stmt = (
            delete(users_table)
            .where(users_table.c.id == user_id)
            .returning(users_table.c.id)  # Возвращаем ID для проверки
        )
        async with self.db.begin():
            result = await self.db.execute(delete_stmt)
        return bool(result.scalar_one_or_none())