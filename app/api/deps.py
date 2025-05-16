import logging
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.connection import get_db_connection
from app.schemas.user import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

api_key_header_auth_scheme = APIKeyHeader(name="Authorization", auto_error=False)

AUTH_SCHEME_PREFIX = "TOKEN"


async def get_current_user(
    authorization_header: Optional[str] = Security(api_key_header_auth_scheme),
    db: AsyncConnection = Depends(get_db_connection),
) -> User:
    if not authorization_header:
        logger.warning("Authentication attempt without Authorization header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": AUTH_SCHEME_PREFIX},
        )

    try:
        scheme, _, api_key = authorization_header.partition(" ")
    except ValueError:
        scheme = ""
        api_key = ""

    if not api_key or scheme.upper() != AUTH_SCHEME_PREFIX:
        logger.warning(
            f"Invalid Authorization header format. Expected '{AUTH_SCHEME_PREFIX} <key>', got '{authorization_header}'"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": AUTH_SCHEME_PREFIX},
        )

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_api_key(api_key)

    if not user:
        logger.warning(
            f"Authentication attempt with invalid API key: {api_key[:10]}..."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": AUTH_SCHEME_PREFIX},
        )

    return user


from app.core.config import get_settings


async def get_current_admin_user(
    authorization_header: Optional[str] = Security(api_key_header_auth_scheme),
) -> bool:
    """
    Проверяет, является ли предоставленный токен валидным админским токеном.
    """
    settings = get_settings()

    if not authorization_header:
        # Админский эндпоинт без авторизации
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
            headers={"WWW-Authenticate": AUTH_SCHEME_PREFIX},
        )

    try:
        scheme, _, provided_token = authorization_header.partition(" ")
    except ValueError:
        scheme = ""
        provided_token = ""

    if (
        scheme.upper() != AUTH_SCHEME_PREFIX
        or provided_token != settings.ADMIN_API_TOKEN
    ):
        logger.warning("Admin authentication failed: invalid token or scheme.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for admin access.",
        )

    logger.info("Admin authenticated successfully.")
    return True
