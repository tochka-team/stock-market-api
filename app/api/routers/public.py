from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.connection import get_db_connection
from app.schemas.instrument import Instrument
from app.schemas.orderbook import L2OrderBook
from app.schemas.transaction import Transaction
from app.schemas.user import NewUser, User
from app.services.auth_service import AuthService
from app.services.instrument_service import InstrumentService
from app.services.orderbook_service import OrderBookService
from app.services.transaction_service import TransactionService

router = APIRouter(tags=["Public Data"])


@router.get(
    "/instrument",
    response_model=List[Instrument],
    summary="Get Available Instruments",
    description="Получение списка всех доступных для торговли инструментов.",
)
async def list_instruments(db: AsyncConnection = Depends(get_db_connection)):
    try:
        instrument_service = InstrumentService(db)
        instruments = await instrument_service.get_all_instruments()
        return instruments
    except Exception as e:
        print(f"Error fetching instruments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch instruments from the database.",
        )


@router.post(
    "/register",
    response_model=User,
    summary="Register User",
    description="Регистрация пользователя в платформе. Обязательна для совершения сделок",
)
async def register(
    user_data: NewUser, db: AsyncConnection = Depends(get_db_connection)
):
    try:
        auth_service = AuthService(db)
        user = await auth_service.register_user(name=user_data.name)
        return user
    except Exception as e:
        print(f"Error registering user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not register user.",
        )


@router.get(
    "/orderbook/{ticker}",
    response_model=L2OrderBook,
    summary="Get Orderbook",
    description="Текущие заявки",
)
async def get_orderbook(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=25),
    db: AsyncConnection = Depends(get_db_connection),
) -> L2OrderBook:
    """
    Получить стакан заявок для указанного тикера
    """
    try:
        orderbook_service = OrderBookService(db)
        orderbook = await orderbook_service.get_orderbook(ticker, limit)

        if not orderbook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Orderbook for ticker {ticker} not found",
            )

        return orderbook
    except Exception as e:
        print(f"Error getting orderbook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch orderbook",
        )


@router.get(
    "/transactions/{ticker}",
    response_model=List[Transaction],
    summary="Get Transaction History",
    description="Получение истории сделок для указанного тикера.",
)
async def get_transaction_history(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncConnection = Depends(get_db_connection),
):
    """
    Эндпоинт для получения истории сделок по тикеру.
    - **ticker**: Тикер инструмента (например, "AAPL").
    - **limit**: Максимальное количество возвращаемых транзакций.
    """
    transaction_service = TransactionService(db)
    try:
        transactions = await transaction_service.get_transactions_by_ticker(
            ticker=ticker, limit=limit
        )
        return transactions
    except Exception as e:
        print(f"API Error - get_transaction_history for {ticker}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching transaction history.",
        )
