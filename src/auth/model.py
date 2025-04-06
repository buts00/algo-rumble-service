from sqlmodel import Field
from sqlalchemy import Column, String, Enum
from sqlalchemy.dialects.postgresql import INTEGER as pg_INTEGER
from enum import Enum as PyEnum

from src.db.model import BaseModel


class UserRole(str, PyEnum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class User(BaseModel, table=True):
    __tablename__ = "users"

    username: str = Field(sa_column=Column(String(50), unique=True))
    password_hash: str = Field(exclude=True)
    role: UserRole = Field(sa_column=Column(Enum(UserRole), default=UserRole.USER))
    rating: int = Field(default=200, sa_column=Column(pg_INTEGER, default=0))
    country_code: str = Field(sa_column=Column(String(5)))
    refresh_token: str = Field(
        sa_column=Column(String(500), nullable=True, default=None)
    )

    def __repr__(self):
        return f"<User {self.username} (Rating: {self.rating})>"
