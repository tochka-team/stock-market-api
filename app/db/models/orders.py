from sqlalchemy import Column, String, Integer, DateTime, Enum
from sqlalchemy.sql import func
import uuid

from app.db.base_class import Base

class OrderStatus(str, Enum):
    NEW = "NEW"
    EXECUTED = "EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    CANCELLED = "CANCELLED"

class OrderDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    direction = Column(String, nullable=False)  # BUY или SELL
    qty = Column(Integer, nullable=False)
    price = Column(Integer, nullable=True)  # null для рыночных заявок
    status = Column(String, nullable=False, default=OrderStatus.NEW)
    filled = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
