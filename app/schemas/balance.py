import uuid

from pydantic import BaseModel, Field


class AdminBalanceChangeRequest(BaseModel):
    user_id: uuid.UUID = Field(description="ID пользователя, чей баланс изменяется")
    ticker: str = Field(description="Тикер актива или валюты (например, 'RUB', 'AAPL')")
    amount: int = Field(
        gt=0, description="Сумма изменения (абсолютное значение, всегда положительное)"
    )
