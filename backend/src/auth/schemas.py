from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, EmailStr
import uuid


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class UserBase(BaseModel):
    username: str = Field(..., max_length=50, examples=["algo_champ"])
    email: EmailStr = Field(..., examples=["user@algorumble.com"])


class UserModel(UserBase):
    uid: uuid.UUID
    role: UserRole
    rating: float
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class UserCreateModel(UserBase):
    password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        examples=["Str0ngP@ss!"],
        description="Must contain at least 8 characters with mix of letters, numbers and symbols",
    )


class UserLoginModel(BaseModel):
    email: EmailStr = Field(..., examples=["user@algorumble.com"])
    password: str = Field(..., min_length=8, max_length=64)
