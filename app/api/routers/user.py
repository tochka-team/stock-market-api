from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.common import OkResponse
from app.schemas.user import User
from app.services.user_service import UserService

router = APIRouter(tags=["User Actions"], dependencies=[Depends(get_current_user)])


@router.delete(
    "/user/{user_id}",
    response_model=OkResponse,
    summary="Delete user",
    description="Удаление пользователя по user_id",
    dependencies=[Depends(get_current_user)],
)
async def delete_user_endpoint(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db_connection),
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user account.",
        )

    user_service = UserService(db)
    try:
        deleted = await user_service.delete_user(user_id=user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found.",
            )
        return OkResponse(success=True)
    except HTTPException:
        raise
    except Exception as e:
        print(f"User delete_user_endpoint error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the user.",
        )
