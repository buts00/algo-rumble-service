from sqlalchemy import Column, String, INTEGER
from sqlmodel import Field
from src.storage.models.base import BaseModel


class User(BaseModel, table=True):
    """Database model for a user."""

    __tablename__ = "users"

    username: str = Field(
        sa_column=Column(String(50), unique=True, nullable=False),
        description="Unique username for the user.",
    )
    password_hash: str = Field(
        sa_column=Column(String(256), nullable=False),
        exclude=True,
        description="Hashed user password.",
    )
    rating: int = Field(
        default=1000,
        sa_column=Column(INTEGER, default=1000, nullable=False),
        description="User's rating for matchmaking.",
    )
    country_code: str = Field(
        sa_column=Column(String(2), nullable=False),
        description="ISO 3166-1 alpha-2 country code.",
    )
    refresh_token: str = Field(
        sa_column=Column(String(500), nullable=True, default=None),
        exclude=True,
        description="JWT refresh token for the user.",
    )
