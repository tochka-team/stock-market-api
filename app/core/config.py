import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
dotenv_path = os.path.join(project_root, ".env")

if os.path.exists(dotenv_path):
    print(f"INFO: Loading .env file from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path, override=True, verbose=True)
else:
    print(
        f"WARNING: .env file not found at {dotenv_path}. Relying on system environment variables."
    )


class Settings(BaseSettings):
    """
    Класс для хранения настроек приложения.
    Pydantic-settings теперь будет читать переменные из окружения,
    которое мы только что (возможно) пополнили/перезаписали из .env.
    """

    DATABASE_URL: str = (
        "sqlite+aiosqlite:///./default_db_should_not_be_used.db"  
    )

    API_V1_STR: str = "/api/v1"

    PROJECT_NAME: str = "Toy Exchange API"

    PROJECT_VERSION: str = "0.1.0"

    ADMIN_API_TOKEN: str = "supersecretadmintoken"

    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )


@lru_cache(maxsize=None)
def get_settings() -> Settings:
    settings_instance = Settings()
    print(
        f"DEBUG (get_settings): DATABASE_URL from Settings instance: '{settings_instance.DATABASE_URL}'"
    )
    return settings_instance
