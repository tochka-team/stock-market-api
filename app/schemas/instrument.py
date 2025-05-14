from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class Instrument(BaseModel):
    """
    Схема инструмента, точно соответствующая openapi.json components.schemas.Instrument.
    Используется для ответа API.
    """
    name: str = Field(description="Название инструмента")
    ticker: str = Field(description="Уникальный тикер инструмента")

    model_config = ConfigDict(from_attributes=True)
