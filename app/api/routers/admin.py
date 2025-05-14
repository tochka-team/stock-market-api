# app/api/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.connection import get_db_connection
from app.schemas.common import OkResponse
from app.schemas.instrument import Instrument
from app.services.instrument_service import InstrumentService

router = APIRouter(
    tags=["Admin Actions"],
    # dependencies=[Depends(тут будет безопасность)]
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the instrument.",
        )
