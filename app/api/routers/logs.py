import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.schemas.logs import LogsRequest, LogsResponse
from app.services.logs_service import LogsService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/logs",
    tags=["Logs"],
)


@router.get(
    "/",
    response_model=LogsResponse,
    summary="Get Application Logs",
    description="Получение логов приложения с возможностью фильтрации по времени и уровню",
)
async def get_logs_endpoint(
    start_time: Optional[str] = Query(
        None, 
        description="Начальное время в ISO формате (например: 2024-01-01T00:00:00)"
    ),
    end_time: Optional[str] = Query(
        None, 
        description="Конечное время в ISO формате (например: 2024-01-01T23:59:59)"
    ),
    level: Optional[str] = Query(
        None, 
        description="Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
    limit: Optional[int] = Query(
        100, 
        description="Максимальное количество записей", 
        ge=1
    ),
    offset: Optional[int] = Query(
        0, 
        description="Смещение для пагинации", 
        ge=0
    ),
):
    """
    Получение логов приложения с фильтрацией
    
    Поддерживаемые параметры:
    - start_time: фильтрация логов начиная с указанного времени
    - end_time: фильтрация логов до указанного времени  
    - level: фильтрация по уровню логирования
    - limit: максимальное количество записей в ответе
    - offset: смещение для пагинации
    """
    try:
        from datetime import datetime
        
        request = LogsRequest(
            start_time=datetime.fromisoformat(start_time) if start_time else None,
            end_time=datetime.fromisoformat(end_time) if end_time else None,
            level=level,
            limit=limit,
            offset=offset,
        )
        
        logs_service = LogsService()
        logs, total_count = await logs_service.get_logs(request)
        
        has_more = (offset + limit) < total_count
        
        return LogsResponse(
            logs=logs,
            total_count=total_count,
            has_more=has_more
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid datetime format: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in get_logs_endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving logs"
        )


@router.get(
    "/tail",
    response_model=LogsResponse,
    summary="Get Recent Logs",
    description="Получение последних логов (аналог tail -f)",
)
async def get_recent_logs_endpoint(
    lines: Optional[int] = Query(
        50, 
        description="Количество последних строк", 
        ge=1
    ),
    level: Optional[str] = Query(
        None, 
        description="Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
):
    """
    Получение последних логов (аналог tail)
    
    Параметры:
    - lines: количество последних строк для получения
    - level: фильтрация по уровню логирования
    """
    try:
        request = LogsRequest(
            level=level,
            limit=lines,
            offset=0,
        )
        
        logs_service = LogsService()
        logs, total_count = await logs_service.get_logs(request)
        
        return LogsResponse(
            logs=logs,
            total_count=total_count,
            has_more=False  
        )
        
    except Exception as e:
        logger.error(f"Error in get_recent_logs_endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving recent logs"
        )


@router.get(
    "/raw",
    summary="Get Raw Logs",
    description="Получение логов в raw формате (plain text) для удобного просмотра",
    response_class=Response,
)
async def get_raw_logs_endpoint(
    start_time: Optional[str] = Query(
        None, 
        description="Начальное время в ISO формате (например: 2024-01-01T00:00:00)"
    ),
    end_time: Optional[str] = Query(
        None, 
        description="Конечное время в ISO формате (например: 2024-01-01T23:59:59)"
    ),
    level: Optional[str] = Query(
        None, 
        description="Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    ),
    limit: Optional[int] = Query(
        100, 
        description="Максимальное количество записей", 
        ge=1
    ),
    lines: Optional[int] = Query(
        None,
        description="Количество последних строк (если указано, игнорирует другие фильтры кроме level)",
        ge=1
    ),
):
    """
    Получение логов в raw формате (plain text)
    
    Если указан параметр lines, возвращает последние N строк логов.
    Иначе применяет фильтрацию по времени и уровню.
    """
    try:
        if lines:
            request = LogsRequest(
                level=level,
                limit=lines,
                offset=0,
            )
        else:
            from datetime import datetime
            
            request = LogsRequest(
                start_time=datetime.fromisoformat(start_time) if start_time else None,
                end_time=datetime.fromisoformat(end_time) if end_time else None,
                level=level,
                limit=limit,
                offset=0,
            )
        
        logs_service = LogsService()
        logs, _ = await logs_service.get_logs(request)
        
        raw_logs = []
        for log_entry in logs:
            timestamp_str = log_entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if log_entry.logger_name:
                log_line = f"[{timestamp_str}] {log_entry.level} {log_entry.logger_name}: {log_entry.message}"
            else:
                log_line = f"[{timestamp_str}] {log_entry.level}: {log_entry.message}"
            raw_logs.append(log_line)
        
        raw_content = "\n".join(raw_logs)
        
        return Response(
            content=raw_content,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache"
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid datetime format: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in get_raw_logs_endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving raw logs"
        ) 