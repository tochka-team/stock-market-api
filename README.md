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

## Внесение изменений в репозиторий

Отлично, добавим главу "Внесение изменений в репозиторий" в README.md. Это поможет стандартизировать рабочий процесс для команды.

--- (Добавьте это в ваш существующий README.md) ---

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

Убедитесь, что DATABASE_URL в .env настроена корректно для вашего локального окружения.

Сгенерируйте миграцию:

```
alembic revision --autogenerate -m "albemic version description"
```

Внимательно просмотрите сгенерированный файл миграции в папке alembic/versions/. Убедитесь, что он содержит только ожидаемые изменения схемы.

Локально примените миграцию для тестирования:

```bash
alembic upgrade head
```

Добавьте сгенерированный файл миграции в коммит вместе с изменениями моделей.

5. Проверка и форматирование кода:

Перед коммитом рекомендуется проверить и отформатировать ваш код для соответствия стандартам.

autoflake --in-place --remove-all-unused-imports --recursive app tests
autopep8 --in-place --recursive app tests

(Рекомендуется) Black и isort:
Для более строгого и единого форматирования рассмотрите использование black (форматер кода) и isort (сортировщик импортов).

# Установка: pip install black isort
isort app tests
black app tests
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

Эти инструменты часто настраиваются для автоматического применения при сохранении в IDE или через pre-commit хуки.

6. Закоммитьте ваши изменения:

Делайте небольшие, логически завершенные коммиты с понятными сообщениями.

git add .  # Или добавьте конкретные файлы
git commit -m "feat: Реализован эндпоинт получения баланса пользователя"
# Используйте префиксы для сообщений коммитов (опционально, но полезно):
# - feat: (новая фича)
# - fix: (исправление бага)
# - docs: (изменения в документации)
# - style: (форматирование, пропущенные точки с запятой и т.д.)
# - refactor: (рефакторинг кода без изменения функциональности)
# - test: (добавление или исправление тестов)
# - chore: (обновление зависимостей, рутинные задачи)
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

7. Отправьте вашу ветку в удаленный репозиторий:

git push origin feature/название-вашей-фичи
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

8. Создайте Pull Request (PR):

Перейдите на страницу вашего репозитория на GitHub (или другой платформе).

GitHub обычно автоматически предлагает создать Pull Request для только что отправленной ветки.

Нажмите "Compare & pull request".

Целевая ветка для слияния должна быть main (или ваша основная ветка разработки).

Напишите информативное название и описание для вашего PR:

Кратко опишите, какие изменения сделаны.

Если PR закрывает какую-либо задачу (issue), укажите ее номер (e.g., "Closes #123").

Назначьте ревьюеров из вашей команды (если это практикуется).

9. Прохождение Code Review и CI (если настроено):

Другие члены команды (или тимлид) просмотрят ваш код, оставят комментарии и предложения.

Внесите необходимые исправления в вашей ветке и запушьте их. PR обновится автоматически.

Если настроены автоматические проверки (CI - Continuous Integration), убедитесь, что они проходят успешно.

10. Слияние Pull Request:

После одобрения и успешного прохождения всех проверок, PR может быть слит в main.

Обычно это делает ответственный за репозиторий или автор PR (если есть права).

Предпочтительный метод слияния: "Squash and merge" (если хотите чистую историю в main с одним коммитом на фичу) или "Merge pull request" (сохраняет все коммиты из ветки). Обсудите это с командой.

После слияния можно удалить вашу ветку фичи из удаленного репозитория (GitHub часто предлагает это сделать).

11. Обновите вашу локальную ветку main:

После того как ваш PR смержен, не забудьте обновить вашу локальную main.

git checkout main
git pull origin main
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

Этот процесс поможет поддерживать порядок в репозитории, улучшить качество кода и облегчить совместную работу.

**Дополнительные замечания:**

*   **Pre-commit хуки:** Для автоматизации шага 5 (проверка и форматирование кода) очень рекомендуется настроить [pre-commit](https://pre-commit.com/). Это инструмент, который запускает указанные проверки (например, `black`, `isort`, `flake8`) перед каждым коммитом и не дает закоммитить код, если проверки не прошли или если форматеры внесли изменения (в этом случае нужно будет добавить измененные файлы и повторить коммит).
*   **Установка `autopep8` и `autoflake`:** Если члены команды еще не установили эти инструменты, им нужно будет это сделать (`pip install autopep8 autoflake`). Лучше всего добавить их в `requirements-dev.txt` (или общий `requirements.txt`, если команда небольшая).

Этот раздел должен дать четкое руководство по процессу разработки.
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
IGNORE_WHEN_COPYING_END

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
*   Функции должны принимать `AsyncConnection` (или `AsyncSession`, если используется сессионный подход) в качестве аргумента.
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

---
