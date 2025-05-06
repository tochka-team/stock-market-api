from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID
from app.db.models.users import UserRole

class NewUser(BaseModel):
    name: str = Field(..., min_length=3, description="Имя пользователя")

class UserBase(BaseModel):
    name: str = Field(..., description="Имя пользователя")
    role: UserRole = Field(None, description="Роль пользователя")

class User(UserBase):
    id: UUID
    api_key: str = Field(..., description="API ключ пользователя")
    model_config = ConfigDict(from_attributes=True)

    
