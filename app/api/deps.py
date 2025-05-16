import logging
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import get_settings
from app.db.connection import get_db_connection
from app.schemas.user import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

user_api_key_scheme = APIKeyHeader(
    name="Authorization",
    auto_error=False,
    description="User API Key. Format: TOKEN <your_api_key>",
)
USER_AUTH_SCHEME_PREFIX = "TOKEN"


async def get_current_user(
    authorization_header: Optional[str] = Security(user_api_key_scheme),
    db: AsyncConnection = Depends(get_db_connection),
) -> User:
    if not authorization_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": USER_AUTH_SCHEME_PREFIX},
        )

    try:
        scheme, _, api_key = authorization_header.partition(" ")
    except ValueError:
        scheme = ""
        api_key = ""

    if not api_key or scheme.upper() != USER_AUTH_SCHEME_PREFIX:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials format.",
            headers={"WWW-Authenticate": USER_AUTH_SCHEME_PREFIX},
        )

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_api_key(api_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key.",
            headers={"WWW-Authenticate": USER_AUTH_SCHEME_PREFIX},
        )

    logger.info(f"User {user.id} authenticated successfully.")
    return user


admin_api_key_scheme = APIKeyHeader(
    name="Authorization",
    auto_error=False,
    description="Admin API Key. Format: TOKEN <your_admin_api_token>",
)
ADMIN_AUTH_SCHEME_PREFIX = "TOKEN"


async def get_current_admin_user(
    authorization_header: Optional[str] = Security(admin_api_key_scheme),
) -> bool:
    settings = get_settings()

    if not authorization_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
            headers={
                "WWW-Authenticate": f'{ADMIN_AUTH_SCHEME_PREFIX} realm="Admin API"'
            },
        )

    try:
        scheme, _, provided_token = authorization_header.partition(" ")
    except ValueError:
        scheme = ""
        provided_token = ""

    if scheme.upper() != ADMIN_AUTH_SCHEME_PREFIX:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme for admin. Expected TOKEN.",
            headers={
                "WWW-Authenticate": f'{ADMIN_AUTH_SCHEME_PREFIX} realm="Admin API"'
            },
        )

    if provided_token != settings.ADMIN_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for admin access. Invalid admin token.",
        )

    logger.info("Admin authenticated successfully.")
    return True
