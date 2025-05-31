import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_admin_user
from app.db.connection import get_db_connection
from app.schemas.balance import AdminBalanceChangeRequest
from app.schemas.common import OkResponse
from app.schemas.instrument import Instrument
from app.schemas.user import User
from app.services.admin_service import AdminService
from app.services.balance_service import BalanceService
from app.services.instrument_service import InstrumentService

router = APIRouter(
    prefix="/admin",
    tags=["Admin Actions"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.delete(
    "/user/{user_id}",
    response_model=User,
    summary="Delete user",
    description="Удаление пользователя по user_id",
)
async def admin_delete_user_endpoint(
    user_id: uuid.UUID, db: AsyncConnection = Depends(get_db_connection)
):
    admin_service = AdminService(db)
    try:
        deleted_user_data = await admin_service.delete_user(user_id=user_id)

        if not deleted_user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{user_id}' not found.",
            )
        return deleted_user_data
    except HTTPException:
        raise
    except Exception as e:
        print(f"Admin delete_user_endpoint error for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the user.",
        )


@router.post(
    "/instrument",
    response_model=OkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add New Instrument",
    description="Добавление нового торгового инструмента администратором.",
)
async def add_instrument_endpoint(
    instrument_data: Instrument, db: AsyncConnection = Depends(get_db_connection)
):
    instrument_service = InstrumentService(db)
    try:
        await instrument_service.add_new_instrument(instrument_data=instrument_data)
        return OkResponse(success=True)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        print(f"Admin add_instrument_endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while adding the instrument.",
        )


@router.delete(
    "/instrument/{ticker}",
    response_model=OkResponse,
    summary="Delete Instrument",
    description="Удаление (делистинг) торгового инструмента администратором.",
)
async def delete_instrument_endpoint(
    ticker: str, db: AsyncConnection = Depends(get_db_connection)
):
    instrument_service = InstrumentService(db)
    try:
        deleted_successfully = await instrument_service.delete_instrument_by_ticker(
            ticker=ticker
        )
        if not deleted_successfully:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instrument with ticker '{ticker}' not found.",
            )
        return OkResponse(success=True)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Admin delete_instrument_endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the instrument.",
        )


@router.post(
    "/balance/deposit",
    response_model=OkResponse,
    summary="Admin Deposit to User Balance",
    description="Пополнение баланса указанного пользователя для указанного тикера.",
    status_code=status.HTTP_200_OK,
)
async def admin_deposit_funds(
    request_data: AdminBalanceChangeRequest,
    db: AsyncConnection = Depends(get_db_connection),
):
    balance_service = BalanceService(db)
    try:
        await balance_service.admin_update_or_create_balance(
            user_id=request_data.user_id,
            ticker=request_data.ticker,
            change_amount=request_data.amount,
            operation="deposit",
        )
        return OkResponse(success=True)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"Admin deposit error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process deposit.",
        )


@router.post(
    "/balance/withdraw",
    response_model=OkResponse,
    summary="Admin Withdraw from User Balance",
    description="Списание с баланса указанного пользователя для указанного тикера.",
    status_code=status.HTTP_200_OK,
)
async def admin_withdraw_funds(
    request_data: AdminBalanceChangeRequest,
    db: AsyncConnection = Depends(get_db_connection),
):
    balance_service = BalanceService(db)
    try:
        await balance_service.admin_update_or_create_balance(
            user_id=request_data.user_id,
            ticker=request_data.ticker,
            change_amount=request_data.amount,
            operation="withdraw",
        )
        return OkResponse(success=True)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"Admin withdraw error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process withdrawal.",
        )
