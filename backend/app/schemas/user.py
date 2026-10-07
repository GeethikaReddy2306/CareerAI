from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    name: str
    email: EmailStr


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserMeResponse(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

