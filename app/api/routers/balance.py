import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.user import User
from app.services.balance_service import BalanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/balance", tags=["Balance"])


@router.get(
    "",
    response_model=Dict[str, int],
    summary="Get User Balances by Ticker",
    description="Получение балансов пользователя по всем имеющимся тикерам",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Необходима аутентификация или неверный API ключ"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Внутренняя ошибка сервера"
        },
    },
)
async def get_balances_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db_connection),
):
    balance_service = BalanceService(db)
    try:
        balances = await balance_service.get_user_balance(user_id=current_user.id)
        return balances
    except Exception as e:
        logger.error(
            f"Error getting balances for user {current_user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve balances.",
        )
