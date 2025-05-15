# app/schemas/balance.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List

# --- Схемы из openapi.json ---
# components.schemas.AssetBalance
class AssetBalance(BaseModel):
    ticker: str = Field(..., description="Тикер актива") # openapi: description
    amount: int = Field(..., description="Количество актива на балансе") # openapi: description, format: int64

    model_config = ConfigDict(from_attributes=True)


# components.schemas.BalanceResponse
class BalanceResponse(BaseModel):
    total_balance: int = Field(..., description="Общий баланс пользователя в копейках (или минимальных единицах валюты)") # openapi: description, format: int64
    assets: List[AssetBalance] = Field(..., description="Список активов на балансе") # openapi: description

    model_config = ConfigDict(from_attributes=True)


# components.schemas.DepositRequest
class DepositRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Сумма пополнения в копейках (или минимальных единицах валюты)") # openapi: description, format: int64. gt=0 добавлено для логической валидации.

    model_config = ConfigDict(from_attributes=True)