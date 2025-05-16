from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Transaction(BaseModel):
    """
    Схема для отображения транзакции в соответствии с openapi.json.
    """

    ticker: str = Field(description="Тикер инструмента, по которому прошла сделка")
    amount: int = Field(description="Количество (объем) актива в сделке")
    price: int = Field(description="Цена за единицу актива в сделке")
    timestamp: datetime = Field(description="Время совершения сделки")
    model_config = ConfigDict(from_attributes=True)
