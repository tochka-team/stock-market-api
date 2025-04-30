from fastapi import APIRouter

from app.api.routers import public


api_router = APIRouter()

api_router.include_router(public.router, prefix="/public")
