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

## Внесение изменений в репозиторий (Workflow)

Следуйте этому процессу при внесении любых изменений в кодовую базу, будь то новая фича, исправление бага или рефакторинг.

**1. Обновите вашу локальную основную ветку:**

Перед созданием новой ветки убедитесь, что ваша локальная копия основной ветки (предположим, это `main`) актуальна.

```bash
git checkout main
git pull origin main
```

**2. Создайте новую ветку для вашей задачи:**

Отведите новую ветку от main. Называйте ветки осмысленно:
```bash
git checkout -b название-ветки
```

**3. Внесите изменения в код:**

Реализуйте необходимую функциональность, следуя "Руководству для разработчиков" (см. ниже).

**4.Создание миграций базы данных (если изменяли модели БД):**

Если вы добавляли или изменяли модели SQLAlchemy (app/db/models/), необходимо создать и проверить миграцию Alembic:

Сгенерируйте миграцию:

```bash
alembic revision --autogenerate -m "albemic version description"
```

Внимательно просмотрите сгенерированный файл миграции в папке alembic/versions/. Убедитесь, что он содержит только ожидаемые изменения схемы.

Локально примените миграцию для тестирования:

```bash
alembic upgrade head
```

Добавьте сгенерированный файл миграции в коммит вместе с изменениями моделей.

**5. Проверка и форматирование кода:**

Перед коммитом рекомендуется проверить и отформатировать ваш код для соответствия стандартам.

```bash
# 1. Удалить неиспользуемые импорты и переменные
autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive app tests

# 2. Отсортировать импорты
isort app tests

# 3. Отформатировать код
black app tests
```

**6. Закоммитьте ваши изменения:**

Делайте небольшие, логически завершенные коммиты с понятными сообщениями.

```bash
git add .  # Или добавьте конкретные файлы
git commit -m "feat: Реализован эндпоинт получения баланса пользователя"
```

**7. Отправьте вашу ветку в удаленный репозиторий:**

```bash
git push
```

**8. Создайте Pull Request (PR):**

- Перейдите на страницу залитой ветки на GitHub.

- Нажмите `Compare & pull request`. Целевая ветка для слияния должна быть main.

- Напишите информативное название и описание для вашего PR

- Уведомите остальных членов команды о необходимости провести ревью.

## Руководство для разработчиков

Этот раздел описывает основные конвенции и шаги для добавления новой функциональности (моделей, схем, эндпоинтов) в проект.

### Основные технологии и принципы

*   **Фреймворк:** FastAPI
*   **База данных:** SQLAlchemy Core (не ORM) для взаимодействия с БД.
*   **Миграции БД:** Alembic.
*   **Валидация данных/Сериализация:** Pydantic схемы.
*   **Асинхронность:** Используйте `async` и `await` для всех операций ввода-вывода (работа с БД, внешние API).
*   **Структура проекта:** Группировка по слоям (api, core, db, schemas, services).
*   **Соответствие OpenAPI:** Все API эндпоинты и схемы данных должны строго соответствовать предоставленному `openapi.json`.

### Шаблон добавления новой сущности и API для нее

Предположим, вам нужно добавить новую сущность (например, "Отзывы" - `Reviews`) и API для работы с ней.

**1. Определение схемы Pydantic (`app/schemas/`)**

*   Создайте/отредактируйте файл в `app/schemas/`, например, `app/schemas/review.py`.
*   Определите Pydantic модели для:
    *   Создания сущности (например, `ReviewCreate`).
    *   Обновления сущности (например, `ReviewUpdate`).
    *   Отображения сущности в API ответах (например, `ReviewResponse` или просто `Review`).
*   Все поля и их типы должны соответствовать определениям в `openapi.json`.
*   Если используются Enum, определите их как `(str, Enum)` внутри соответствующего файла схем и импортируйте оттуда в модели БД.

    *Пример (`app/schemas/review.py`):*
    ```python
    from pydantic import BaseModel, Field
    from enum import Enum
    from typing import Optional
    import uuid
    from datetime import datetime

    class ReviewRating(int, Enum):
        ONE_STAR = 1
        # ...
        FIVE_STARS = 5

    class ReviewCreate(BaseModel):
        text: str = Field(..., max_length=1000)
        rating: ReviewRating
        item_ticker: str # Пример связи с другим объектом

    class ReviewResponse(ReviewCreate):
        id: uuid.UUID
        user_id: uuid.UUID
        created_at: datetime
        # model_config = ConfigDict(from_attributes=True) # Если читаете из SQLAlchemy объектов
    ```

**2. Определение модели БД (`app/db/models/`)**

*   Создайте/отредактируйте файл в `app/db/models/`, например, `app/db/models/reviews.py`.
*   Определите таблицу с использованием `sqlalchemy.Table` и нашего общего `metadata` из `app.db.metadata`.
*   Колонки должны соответствовать полям, которые необходимо хранить.
*   Используйте `GenericUUID` для ID, если это UUID.
*   Используйте `SqlEnum` для Enum-типов, импортируя Enum из соответствующего файла схем (`from app.schemas.review import ReviewRating`).
*   Добавьте необходимые индексы (`index=True` для отдельных колонок или `Index("имя_индекса", "колонка1", "колонка2")` для составных).
*   Импортируйте новую таблицу в `app/db/models/__init__.py` и добавьте ее в `__all__`.

    *Пример (`app/db/models/reviews.py`):*
    ```python
    import uuid
    from sqlalchemy import Table, Column, Text, DateTime, func, Index
    from sqlalchemy import Enum as SqlEnum
    from sqlalchemy import UUID as GenericUUID
    from app.db.metadata import metadata
    from app.schemas.review import ReviewRating # Импорт Enum

    reviews_table = Table(
        "reviews",
        metadata,
        Column("id", GenericUUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("user_id", GenericUUID(as_uuid=True), nullable=False, index=True),
        Column("item_ticker", String(20), nullable=False, index=True),
        Column("text", Text, nullable=False),
        Column("rating", SqlEnum(ReviewRating, name="review_rating_enum", create_type=False), nullable=False),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    ```

**3. Создание и применение миграции Alembic**

*   После определения модели в п.2, сгенерируйте новую миграцию:
    ```bash
    # Убедитесь, что DATABASE_URL в .env настроена
    alembic revision --autogenerate -m "Add reviews table"
    ```
*   **Внимательно просмотрите** сгенерированный файл миграции в `alembic/versions/`. Убедитесь, что он корректно создает таблицу и индексы.
*   Примените миграцию:
    ```bash
    alembic upgrade head
    ```

**4. Реализация сервисной логики (`app/services/`)**

*   Создайте/отредактируйте файл в `app/services/`, например, `app/services/review_service.py`.
*   Напишите `async` функции для выполнения CRUD-операций (Create, Read, Update, Delete) или другой бизнес-логики.
*   Функции должны принимать `AsyncConnection` в качестве аргумента.
*   Используйте SQLAlchemy Core выражения (`select`, `insert`, `update`, `delete`) для взаимодействия с БД.
*   Сервисные функции должны принимать Pydantic-схемы для входных данных (например, `ReviewCreate`) и возвращать Pydantic-схемы для выходных данных (например, `ReviewResponse`) или другие необходимые типы.
*   Обрабатывайте возможные исключения SQLAlchemy (например, `IntegrityError`, `NoResultFound`) и либо перевыбрасывайте их, либо преобразуйте в специфичные для сервиса исключения.

    *Пример (`app/services/review_service.py`):*
    ```python
    from sqlalchemy import select, insert
    from sqlalchemy.ext.asyncio import AsyncConnection
    from typing import List, Optional
    import uuid
    from app.db.models.reviews import reviews_table
    from app.schemas.review import ReviewCreate, ReviewResponse

    class ReviewService:
        def __init__(self, db: AsyncConnection):
            self.db = db

        async def create_review(self, user_id: uuid.UUID, review_data: ReviewCreate) -> ReviewResponse:
            stmt = insert(reviews_table).values(
                user_id=user_id,
                item_ticker=review_data.item_ticker,
                text=review_data.text,
                rating=review_data.rating,
            ).returning(reviews_table)
            result = await self.db.execute(stmt)
            await self.db.commit() # Не забывайте коммитить изменения
            created_row = result.mappings().one()
            return ReviewResponse.model_validate(created_row)

        async def get_reviews_for_item(self, item_ticker: str) -> List[ReviewResponse]:
            stmt = select(reviews_table).where(reviews_table.c.item_ticker == item_ticker)
            result = await self.db.execute(stmt)
            rows = result.mappings().all()
            return [ReviewResponse.model_validate(row) for row in rows]
    ```

**5. Реализация API эндпоинтов (`app/api/routers/`)**

*   Создайте/отредактируйте файл в `app/api/routers/`, например, `app/api/routers/review.py`.
*   Создайте `APIRouter`.
*   Определите `async` функции для каждого эндпоинта, используя декораторы FastAPI (`@router.get`, `@router.post` и т.д.).
*   Укажите `response_model` для автоматической сериализации и документации ответа.
*   Используйте `Depends` для внедрения зависимостей (например, `db: AsyncConnection = Depends(get_db_connection)`, `current_user: User = Depends(get_current_user)`).
*   Внутри эндпоинта вызывайте соответствующие сервисные функции.
*   Обрабатывайте исключения, приходящие из сервисного слоя, и преобразуйте их в `HTTPException` с соответствующими статус-кодами.

    *Пример (`app/api/routers/review.py`):*
    ```python
    from fastapi import APIRouter, Depends, HTTPException, status
    from sqlalchemy.ext.asyncio import AsyncConnection
    from typing import List
    import uuid # Пример
    from app.db.connection import get_db_connection
    from app.schemas.review import ReviewCreate, ReviewResponse
    from app.services.review_service import ReviewService
    # from app.api.deps import get_current_user # Пример зависимости аутентификации
    # from app.schemas.user import User # Пример

    router = APIRouter(prefix="/reviews", tags=["Reviews"])

    @router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
    async def create_new_review(
        review_in: ReviewCreate,
        db: AsyncConnection = Depends(get_db_connection),
        # current_user: User = Depends(get_current_user) # Пример
    ):
        # user_id = current_user.id # Пример получения ID пользователя
        user_id_placeholder = uuid.uuid4() # Заглушка, пока нет аутентификации
        review_service = ReviewService(db)
        try:
            created_review = await review_service.create_review(user_id=user_id_placeholder, review_data=review_in)
            return created_review
        except Exception as e: # Конкретизируйте типы исключений
            # logger.error(...)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    ```

**6. Подключение роутера (`app/api/v1.py`)**

*   Импортируйте ваш новый роутер в `app/api/v1.py`.
*   Подключите его к `api_router` с помощью `api_router.include_router(...)`, указав префикс и теги.

**7. Написание тестов (`tests/`)**

*   Для каждого нового эндпоинта крайне желательно написать интеграционные тесты с использованием `pytest` и `httpx`.
*   Тесты должны проверять как успешные сценарии, так и обработку ошибок.

### Стиль кода и Линтинг

*   Придерживайтесь PEP 8.
*   Используйте линтер (например, Flake8) и форматер (например, Black, isort) для поддержания единого стиля кода. (Рекомендуется настроить их в вашем IDE или как pre-commit хуки).

### Работа с Git

*   Создавайте отдельную ветку для каждой новой фичи или исправления.
*   Пишите понятные сообщения коммитов.
*   Используйте Pull Requests для слияния в основную ветку (`main` или `develop`).
*   Проводите Code Review перед слиянием PR.
