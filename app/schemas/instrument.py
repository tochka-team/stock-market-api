from pydantic import BaseModel, ConfigDict, Field


class Instrument(BaseModel):
    name: str = Field(description="Название инструмента")
    ticker: str = Field(description="Уникальный тикер инструмента")

    model_config = ConfigDict(from_attributes=True)
