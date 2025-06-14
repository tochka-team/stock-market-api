from pydantic import BaseModel, ConfigDict, Field


class Instrument(BaseModel):
    name: str = Field(description="Название инструмента")
    ticker: str = Field(
        description="Уникальный тикер инструмента", pattern=r"^[A-Z]{2,10}$"
    )

    model_config = ConfigDict(from_attributes=True)
