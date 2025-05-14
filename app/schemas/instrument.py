from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class Instrument(BaseModel):
    id: int
    name: str = Field(description="Название инструмента")
    ticker: str = Field(description="Уникальный тикер инструмента")
    description: Optional[str] = Field(None, description="Краткое описание инструмента")

    model_config = ConfigDict(from_attributes=True)
