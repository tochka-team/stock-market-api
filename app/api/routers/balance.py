import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.balance import BalanceResponse, DepositRequest
from app.schemas.user import User
from app.services.balance_service import BalanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/balance", tags=["Balance"])


@router.get(
    "/",
    response_model=BalanceResponse,
    summary="Get User Balance",
    description="Получение текущего баланса пользователя, включая денежные средства и активы.",
    responses={  # Добавляем описание ошибок из OpenAPI
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Необходима аутентификация или неверный API ключ"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Внутренняя ошибка сервера"
        },
    },
)
async def get_balance_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db_connection),
):
    balance_service = BalanceService(db)
    try:
        balance = await balance_service.get_user_balance(user_id=current_user.id)
        return balance
    except Exception as e:
        logger.error(
            f"Error getting balance for user {current_user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve balance.",
        )


@router.post(
    "/deposit",
    response_model=BalanceResponse,
    summary="Deposit to Balance",
    description="Пополнение денежного баланса пользователя.",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Некорректные данные для пополнения"
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Необходима аутентификация или неверный API ключ"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Внутренняя ошибка сервера"
        },
    },
)
async def deposit_funds_endpoint(
    deposit_data: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db_connection),
):
    balance_service = BalanceService(db)
    try:
        updated_balance = await balance_service.deposit_to_balance(
            user_id=current_user.id, deposit_amount=deposit_data.amount
        )
        return updated_balance
    except ValueError as ve:
        logger.warning(f"Invalid deposit attempt for user {current_user.id}: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(
            f"Error depositing funds for user {current_user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process deposit.",
        )
