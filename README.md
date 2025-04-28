# Stock Market API

## Локальный запуск на Windows

1. Подготовьте виртуальное окружение

    ```bash
    python -m venv .venv
    source .venv/Scripts/activate
    pip install requirements.txt
    ```

2. Скопируйте и дополните .env
    
    ```bash
    cp .env.example .env
    nano .env
    ```

3. Запустите проект

    ```bash
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```