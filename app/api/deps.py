import logging  # Рекомендуется добавить логирование

from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.connection import get_db_connection
from app.schemas.user import User  # Убедись, что путь корректный
from app.services.auth_service import AuthService  # Убедись, что путь корректный

logger = logging.getLogger(__name__)

# Имя заголовка из openapi.json: securitySchemes.ApiKeyAuth.name
api_key_header_scheme = APIKeyHeader(name="X-API-KEY", auto_error=False)


async def get_current_user(
    api_key: str = Security(api_key_header_scheme),
    db: AsyncConnection = Depends(get_db_connection),
) -> User:
    if not api_key:
        logger.warning("Authentication attempt without API key.")
        # OpenAPI: /balance -> get -> responses -> 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",  # OpenAPI: "Необходима аутентификация"
            headers={"WWW-Authenticate": "APIKey"},  # Стандартный заголовок для 401
        )

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_api_key(api_key)

    if not user:
        logger.warning(
            f"Authentication attempt with invalid API key: {api_key[:10]}..."
        )  # Не логгируй весь ключ
        # OpenAPI: /balance -> get -> responses -> 401 (также подходит для невалидного ключа)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",  # OpenAPI: "Неверный API ключ"
            headers={"WWW-Authenticate": "APIKey"},
        )
    # logger.info(f"User {user.id} authenticated successfully.") # Можно добавить для отладки
    return user
