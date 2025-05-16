from typing import List

from pydantic import BaseModel, ConfigDict, Field


class AssetBalance(BaseModel):
    ticker: str = Field(..., description="Тикер актива")
    amount: int = Field(..., description="Количество актива на балансе")

    model_config = ConfigDict(from_attributes=True)


# components.schemas.BalanceResponse
class BalanceResponse(BaseModel):
    total_balance: int = Field(
        ...,
        description="Общий баланс пользователя в копейках (или минимальных единицах валюты)",
    )
    assets: List[AssetBalance] = Field(..., description="Список активов на балансе")

    model_config = ConfigDict(from_attributes=True)


# components.schemas.DepositRequest
class DepositRequest(BaseModel):
    amount: int = Field(
        ...,
        gt=0,
        description="Сумма пополнения в копейках (или минимальных единицах валюты)",
    )

    model_config = ConfigDict(from_attributes=True)
