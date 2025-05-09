# Stock Market API

## Локальный запуск на Windows

1. Подготовьте виртуальное окружение

    ```bash
    python -m venv .venv
    source .venv/Scripts/activate
    pip install -r requirements.txt
    ```

2. Скопируйте и дополните .env
    
    ```bash
    cp .env.example .env
    nano .env
    ```

3. Примените миграции и запустите проект

    ```bash
    alembic upgrade head
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```

После успешного запуска сервер будет доступен по адресу http://localhost:8000:

- Интерактивная документация (Swagger UI): http://localhost:8000/api/v1/docs

- Альтернативная документация (ReDoc): http://localhost:8000/api/v1/redoc

