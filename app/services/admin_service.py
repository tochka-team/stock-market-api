import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.users import users_table
from app.schemas.user import User

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def delete_user(self, user_id: UUID) -> Optional[User]:
        """
        Удаляет пользователя по ID.
        Сначала загружает пользователя, чтобы вернуть его данные, затем удаляет.
        Возвращает объект удаленного пользователя или None, если пользователь не найден.
        """
        logger.info(f"Admin attempt to delete user with ID: {user_id}")

        get_user_stmt = select(users_table).where(users_table.c.id == user_id)
        user_result = await self.db.execute(get_user_stmt)
        user_to_delete_row = user_result.mappings().one_or_none()

        if not user_to_delete_row:
            logger.warning(f"Admin: User with ID {user_id} not found for deletion.")
            return None

        user_data_to_return = User.model_validate(user_to_delete_row)

        delete_stmt = (
            delete(users_table)
            .where(users_table.c.id == user_id)
            .returning(users_table.c.id)
        )

        delete_result = await self.db.execute(delete_stmt)
        deleted_id = delete_result.scalar_one_or_none()

        if not deleted_id:
            logger.error(
                f"Admin: Failed to delete user {user_id} even though they were found. This should not happen."
            )
            raise Exception(f"Failed to confirm deletion of user {user_id}")

        logger.info(
            f"Admin: Successfully deleted user {user_id} (Name: {user_data_to_return.name}). Returning user data."
        )
        return user_data_to_return
