import uuid
from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, conint


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
    price: Optional[int] = None
    status: OrderStatus
    filled_qty: int = Field(default=0, alias="filled")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MarketOrderResponse(BaseModel):
    """MarketOrder response - БЕЗ поля filled согласно OpenAPI спецификации"""
    id: uuid.UUID
    status: OrderStatus
    user_id: uuid.UUID
    timestamp: datetime
    body: MarketOrderBody

    model_config = ConfigDict(from_attributes=True)


class LimitOrderResponse(BaseModel):
    """LimitOrder response - С полем filled согласно OpenAPI спецификации"""
    id: uuid.UUID
    status: OrderStatus
    user_id: uuid.UUID
    timestamp: datetime
    body: LimitOrderBody
    filled: int = Field(default=0)

    model_config = ConfigDict(from_attributes=True)


AnyOrderResponse = Union[MarketOrderResponse, LimitOrderResponse]


class CreateOrderResponse(BaseModel):
    success: Literal[True] = True
    order_id: uuid.UUID
