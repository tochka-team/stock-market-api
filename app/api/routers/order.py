import logging
import uuid
from typing import List, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.order import (
    CreateOrderResponse,
    LimitOrderBody,
    MarketOrderBody,
    OrderBase,
)
from app.schemas.user import User
from app.services.order_service import OrderService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/order", tags=["Orders"], dependencies=[Depends(get_current_user)]
)

OrderBody = Union[LimitOrderBody, MarketOrderBody]


@router.post(
    "",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Order",
    description="Создание новой рыночной или лимитной заявки.",
)
async def create_order_endpoint(
    order_payload: OrderBody = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db_connection),
):
    order_service = OrderService(db)
    try:
        created_order = await order_service.create_order(
            current_user=current_user, order_data=order_payload
        )
        return CreateOrderResponse(order_id=created_order.id)
    except Exception as e:
        logger.error(
            f"Error creating order for user {current_user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not create order: {str(e)}",
        )


@router.get(
    "/{order_id}",
    response_model=OrderBase,
    summary="Get Order Details",
    description="Получение информации о конкретной заявке пользователя.",
)
async def get_order_details_endpoint(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db_connection),
):
    order_service = OrderService(db)
    order = await order_service.get_order_by_id_for_user(
        order_id=order_id, user_id=current_user.id
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID '{order_id}' not found or does not belong to the current user.",
        )
    return order


@router.get(
    "",
    response_model=List[OrderBase],
    summary="List User Orders",
    description="Получение списка всех заявок пользователя (в будущем можно добавить фильтры).",
)
async def list_user_orders_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db_connection),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    order_service = OrderService(db)
    orders = await order_service.get_orders_by_user(
        user_id=current_user.id, limit=limit, offset=offset
    )
    return orders
