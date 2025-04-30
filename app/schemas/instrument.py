from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class InstrumentBase(BaseModel):
    ticker: str = Field(..., description="Уникальный тикер инструмента (e.g., 'AAPL', 'MEMCOIN')")
    name: Optional[str] = Field(None, description="Полное название инструмента (e.g., 'Apple Inc.', 'Meme Coin')")
    description: Optional[str] = Field(None, description="Краткое описание инструмента")


class Instrument(InstrumentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
