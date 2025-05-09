from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.database import get_db_connection
from app.schemas.orderbook import L2OrderBook
from app.services.orderbook_service import OrderBookService

router = APIRouter()

@router.get("/orderbook/{ticker}", response_model=L2OrderBook)
async def get_orderbook(
    ticker: str,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncConnection = Depends(get_db_connection)
) -> L2OrderBook:
    """
    Получить стакан заявок для указанного тикера
    """
    service = OrderBookService(db)
    orderbook = await service.get_orderbook(ticker, limit)
    
    if orderbook is None:
        raise HTTPException(
            status_code=404,
            detail=f"Instrument with ticker {ticker} not found"
        )
    
    return orderbook 