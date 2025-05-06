# app/api/routers/public.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection
from typing import List

from app.db.connection import get_db_connection
from app.schemas.instrument import Instrument
from app.services.instrument_service import get_all_instruments
from app.schemas.user import NewUser, User
from app.services.auth_service import AuthService


router = APIRouter(tags=["Public Data"])


@router.get(
    "/instrument",
    response_model=List[Instrument],
    summary="Get Available Instruments",
    description="Получение списка всех доступных для торговли инструментов."
)
async def list_instruments(
    db: AsyncConnection = Depends(get_db_connection)
):
    try:
        instruments = await get_all_instruments(db=db)
        return instruments
    except Exception as e:
        print(f"Error fetching instruments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch instruments from the database.",
        )

# ручка для решистрации пользователя. Было принято решение ввести её в файл public.py
@router.post(
    "/register",
    response_model=User,
    summary="Register User",
    description="Регистрация пользователя в платформе. Обязательна для совершения сделок"
)
async def register(
    user_data: NewUser,
    db: AsyncConnection = Depends(get_db_connection)
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

