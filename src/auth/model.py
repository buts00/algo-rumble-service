import os
from enum import Enum as PyEnum

from sqlalchemy import Column, Enum, Integer, String
from sqlalchemy.dialects.postgresql import INTEGER as pg_INTEGER
from sqlmodel import Field

from src.db.model import BaseModel

# Use a different column type for INTEGER in tests (SQLite compatibility)
if os.environ.get("TESTING") == "True":
    INTEGER_TYPE = Integer
else:
    INTEGER_TYPE = pg_INTEGER


class UserRole(str, PyEnum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class User(BaseModel, table=True):
    __tablename__ = "users"

    username: str = Field(sa_column=Column(String(50), unique=True))
    password_hash: str = Field(exclude=True)
    role: UserRole = Field(sa_column=Column(Enum(UserRole), default=UserRole.USER))
    rating: int = Field(default=1000, sa_column=Column(INTEGER_TYPE, default=1000))
    country_code: str = Field(sa_column=Column(String(5)))
    refresh_token: str = Field(
        sa_column=Column(String(500), nullable=True, default=None)
    )

    def __repr__(self):
        return f"<User {self.username} (Rating: {self.rating})>"
