from fastapi import APIRouter

from app.api.routers import admin, public

api_router = APIRouter()

api_router.include_router(public.router, prefix="/public")
api_router.include_router(admin.router, prefix="/admin")
