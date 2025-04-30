import logging
from contextlib import asynccontextmanager
import uvicorn

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import get_settings
from app.db.connection import check_db_connection, close_db_connection


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("--- Application startup ---")
    logger.info(f"Project Name: {settings.PROJECT_NAME}")
    logger.info(f"API Version: {settings.PROJECT_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    try:
        logger.info("Checking database connection...")
        await check_db_connection()
        logger.info("Database connection checked successfully.")
    except ConnectionError as e:
        logger.error(f"FATAL: Database connection failed during startup: {e}")
        logger.warning("Proceeding without guaranteed database connection...")

    yield

    logger.info("--- Application shutdown ---")
    await close_db_connection()
    logger.info("Database connection pool closed.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)


@app.get("/ping", tags=["Health Check"])
async def ping():
    logger.info("Ping received")
    return {"message": "pong"}


app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    print("Starting Uvicorn server directly...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
