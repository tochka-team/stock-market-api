# app/api/routers/balance.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.connection import get_db_connection
from app.schemas.balance import BalanceResponse, DepositRequest
from app.schemas.user import User # Для типизации current_user
from app.services.balance_service import BalanceService
from app.api.deps import get_current_user # Ваша зависимость аутентификации

logger = logging.getLogger(__name__)

# Префикс и теги из OpenAPI: paths -> /balance -> get -> tags: ["Balance"]
router = APIRouter(prefix="/balance", tags=["Balance"])

@router.get(
    "/", # Эндпоинт /balance
    response_model=BalanceResponse, # OpenAPI: responses -> 200 -> content -> application/json -> schema -> $ref: '#/components/schemas/BalanceResponse'
    summary="Get User Balance", # OpenAPI: summary
    description="Получение текущего баланса пользователя, включая денежные средства и активы.", # OpenAPI: description (если есть, берем оттуда, или пишем свой)
    responses={ # Добавляем описание ошибок из OpenAPI
        status.HTTP_401_UNAUTHORIZED: {"description": "Необходима аутентификация или неверный API ключ"}, # OpenAPI: /balance -> get -> responses -> 401 -> description
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Внутренняя ошибка сервера"}, # OpenAPI: /balance -> get -> responses -> 500 -> description
    }
)
async def get_balance_endpoint( # Используем суффикс _endpoint чтобы не конфликтовать с импортами
    current_user: User = Depends(get_current_user), # OpenAPI: security -> ApiKeyAuth
    db: AsyncConnection = Depends(get_db_connection),
):
    balance_service = BalanceService(db)
    try:
        balance = await balance_service.get_user_balance(user_id=current_user.id)
        return balance
    except Exception as e:
        logger.error(f"Error getting balance for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve balance.", # Можно взять из OpenAPI, если там "Внутренняя ошибка сервера"
        )

@router.post(
    "/deposit", # Эндпоинт /balance/deposit
    response_model=BalanceResponse, # OpenAPI: responses -> 200 -> content -> application/json -> schema -> $ref: '#/components/schemas/BalanceResponse'
    summary="Deposit to Balance", # OpenAPI: summary
    description="Пополнение денежного баланса пользователя.", # OpenAPI: description
    status_code=status.HTTP_200_OK, # OpenAPI явно не указывает 201 для POST /deposit, обычно 200 если есть тело ответа
                                    # Если бы не было тела ответа, мог бы быть 204.
                                    # Если бы создавался новый РЕСУРС депозита, мог бы быть 201.
                                    # Здесь мы модифицируем баланс и возвращаем его.
    responses={ # Добавляем описание ошибок из OpenAPI
        status.HTTP_400_BAD_REQUEST: {"description": "Некорректные данные для пополнения"}, # OpenAPI: /balance/deposit -> post -> responses -> 400 -> description
        status.HTTP_401_UNAUTHORIZED: {"description": "Необходима аутентификация или неверный API ключ"}, # OpenAPI: /balance/deposit -> post -> responses -> 401 -> description
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Внутренняя ошибка сервера"}, # OpenAPI: /balance/deposit -> post -> responses -> 500 -> description
    }
)
async def deposit_funds_endpoint(
    deposit_data: DepositRequest, # OpenAPI: requestBody -> content -> application/json -> schema -> $ref: '#/components/schemas/DepositRequest'
    current_user: User = Depends(get_current_user), # OpenAPI: security -> ApiKeyAuth
    db: AsyncConnection = Depends(get_db_connection),
):
    balance_service = BalanceService(db)
    try:
        # Pydantic уже проверил deposit_data.amount > 0 из-за gt=0 в схеме
        updated_balance = await balance_service.deposit_to_balance(
            user_id=current_user.id, deposit_amount=deposit_data.amount
        )
        return updated_balance
    except ValueError as ve: # Если сервис кидает ValueError для бизнес-логики
        logger.warning(f"Invalid deposit attempt for user {current_user.id}: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve), # Можно взять из OpenAPI "Некорректные данные для пополнения"
        )
    except Exception as e:
        logger.error(f"Error depositing funds for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process deposit.",
        )