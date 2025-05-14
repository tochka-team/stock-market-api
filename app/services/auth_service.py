import uuid
import logging
from typing import Optional

from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.users import users_table, UserRole
from app.schemas.user import User

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, name: str) -> User:
        """
        Register a new user
        """
        try:
            # Generate unique ID and API key
            user_id = str(uuid.uuid4())
            api_key = f"key-{uuid.uuid4()}"
            logger.info(f"Generated API key for user {name}")

            # Create new user
            query = insert(users_table).values(
                id=user_id,
                name=name,
                api_key=api_key,
                role=UserRole.USER.value
            ).returning(users_table)

            logger.info("Executing insert query")
            result = await self.db.execute(query)
            logger.info("Committing transaction")
            await self.db.commit()

            row = result.mappings().first()
            logger.info(f"Successfully created user with id {row['id']}")

            return User(
                id=row['id'],
                name=row['name'],
                role=row['role'],
                api_key=row['api_key']
            )
        except Exception as e:
            logger.error(f"Error registering user: {str(e)}", exc_info=True)
            await self.db.rollback()
            raise

    async def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """
        Get user by API key
        """
        try:
            query = select(users_table).where(users_table.c.api_key == api_key)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()

            if user:
                return User(
                    id=str(user.id),
                    name=user.name,
                    role=user.role,
                    api_key=user.api_key
                )
            return None
        except Exception as e:
            logger.error(
                f"Error getting user by API key: {str(e)}", exc_info=True)
            raise
