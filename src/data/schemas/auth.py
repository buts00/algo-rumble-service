import uuid
from enum import Enum

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class UserBase(BaseModel):
    username: str = Field(..., max_length=50, examples=["algo_champ"])
    country_code: str = Field(
        ...,
        max_length=10,
        examples=["UA", "US", "GB"],
        description="ISO 3166-1 alpha-2 country code",
    )


class UserModel(UserBase):
    id: uuid.UUID
    role: UserRole
    rating: int

    model_config = {"from_attributes": True}


class UserCreateModel(UserBase):
    password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        examples=["Str0ngP@ss!"],
        description="Must contain at least 8 characters with mix of letters, numbers and symbols",
    )


class UserLoginModel(BaseModel):
    username: str = Field(..., max_length=50, examples=["algo_champ"])
    password: str = Field(..., min_length=8, max_length=64)


class UserBaseResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: UserRole

    model_config = {"from_attributes": True}


class UserResponseModel(UserBaseResponse):
    rating: int
    country_code: str

    model_config = {"from_attributes": True}