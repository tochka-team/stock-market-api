from fastapi import APIRouter

from app.api.routers import admin, balance, logs, order, public, user

api_router = APIRouter()

api_router.include_router(public.router)
api_router.include_router(admin.router)
api_router.include_router(balance.router)
api_router.include_router(user.router)
api_router.include_router(order.router)
api_router.include_router(logs.router)
