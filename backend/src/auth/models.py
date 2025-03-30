from sqlmodel import SQLModel, Field, Column, String, Enum
import sqlalchemy.dialects.postgresql as pg
from datetime import datetime
import uuid
from enum import Enum as PythonEnum


class UserRole(str, PythonEnum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class User(SQLModel, table=True):
    __tablename__ = "users"

    uid: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID,
            nullable=False,
            primary_key=True,
            default=uuid.uuid4,
        )
    )
    username: str = Field(sa_column=Column(String(50), unique=True))
    password_hash: str = Field(exclude=True)
    email: str = Field(sa_column=Column(String(100), unique=True))
    role: UserRole = Field(sa_column=Column(Enum(UserRole), default=UserRole.USER))
    rating: float = Field(
        default=0.0, sa_column=Column(pg.DOUBLE_PRECISION, default=0.0)
    )
    is_verified: bool = Field(default=False)
    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default_factory=datetime.now)
    )
    updated_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP, default_factory=datetime.now)
    )

    def __repr__(self):
        return f"<User {self.username} (Rating: {self.rating})>"
