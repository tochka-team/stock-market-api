from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Класс для хранения настроек приложения.
    Значения по умолчанию берутся из переменных окружения или файла .env.
    """

    DATABASE_URL: str = "sqlite+aiosqlite:///./stock_market.db"

    API_V1_STR: str = "/api/v1"

    PROJECT_NAME: str = "Toy Exchange API"
    PROJECT_VERSION: str = "0.1.0"

    ADMIN_API_TOKEN: str = "supersecretadmintoken"

    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore'
    )


@lru_cache(maxsize=None)
def get_settings() -> Settings:
    """Возвращает экземпляр настроек приложения."""
    return Settings()
