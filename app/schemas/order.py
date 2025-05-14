import uuid
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, conint
from typing import List, Optional, Literal


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    NEW = "NEW"
    EXECUTED = "EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    CANCELLED = "CANCELLED"


class Level(BaseModel):
    price: int
    qty: int


class L2OrderBook(BaseModel):
    bid_levels: List[Level]
    ask_levels: List[Level]


class MarketOrderBody(BaseModel):
    direction: Direction
    ticker: str
    qty: conint(ge=1)


class LimitOrderBody(BaseModel):
    direction: Direction
    ticker: str
    qty: conint(ge=1)
    price: int


class OrderBase(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    timestamp: datetime
    direction: Direction
    ticker: str
    qty: int
    status: OrderStatus
    filled_qty: int = Field(default=0, alias="filled")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MarketOrderResponse(OrderBase):
    # У рыночного ордера нет 'price' в теле запроса, но он может появиться после исполнения
    # или мы можем не хранить его как отдельное поле в ордере, а вычислять среднюю цену исполнения.
    # Для простоты пока оставим так.
    pass


class LimitOrderResponse(OrderBase):
    price: int


class CreateOrderResponse(BaseModel):
    success: Literal[True] = True
    order_id: uuid.UUID
