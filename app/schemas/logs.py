from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str
    logger_name: Optional[str] = None


class LogsRequest(BaseModel):
    start_time: Optional[datetime] = Field(
        None, description="Начальное время для фильтрации логов (ISO format)"
    )
    end_time: Optional[datetime] = Field(
        None, description="Конечное время для фильтрации логов (ISO format)"
    )
    level: Optional[str] = Field(
        None, description="Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    limit: Optional[int] = Field(
        100, description="Максимальное количество записей", ge=1
    )
    offset: Optional[int] = Field(0, description="Смещение для пагинации", ge=0)


class LogsResponse(BaseModel):
    logs: List[LogEntry]
    total_count: int
    has_more: bool
