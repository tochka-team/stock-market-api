import logging
import uuid
from typing import Optional

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.models.users import users_table
from app.schemas.user import User, UserRole

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncConnection):
        self.db = db

    async def register_user(self, name: str) -> User:
        try:
            user_id_obj: uuid.UUID = uuid.uuid4()
            api_key = f"key-{uuid.uuid4()}"
            logger.info(f"Generated API key for user {name}")

            query = (
                insert(users_table)
                .values(id=user_id_obj, name=name, api_key=api_key, role=UserRole.USER)
                .returning(
                    users_table.c.id,
                    users_table.c.name,
                    users_table.c.role,
                    users_table.c.api_key,
                )
            )

            logger.info("Executing insert query")
            result = await self.db.execute(query)

            created_row_map = result.mappings().first()

            if not created_row_map:
                logger.error(
                    f"User creation failed for {name}, no row returned from DB."
                )
                raise Exception("User registration failed unexpectedly.")

            logger.info(f"Successfully created user with id {created_row_map['id']}")

            return User.model_validate(created_row_map)

        except Exception as e:
            logger.error(f"Error registering user: {str(e)}", exc_info=True)
            raise

    async def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        query = select(users_table).where(users_table.c.api_key == api_key)
        result = await self.db.execute(query)
        user_row_map = result.mappings().first()

        if user_row_map:
            return User.model_validate(user_row_map)
        return None
