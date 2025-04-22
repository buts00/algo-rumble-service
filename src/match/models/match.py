import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Integer
from sqlmodel import Field, SQLModel

from src.db.model import UUID_TYPE


class MatchStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class Match(SQLModel, table=True):
    __tablename__ = "matches"

    id: int = Field(primary_key=True, index=True)
    player1_id: uuid.UUID = Field(sa_column=Column(UUID_TYPE, nullable=False))
    player2_id: uuid.UUID = Field(sa_column=Column(UUID_TYPE, nullable=False))
    winner_id: uuid.UUID = Field(sa_column=Column(UUID_TYPE, nullable=True))
    problem_id: int = Field(sa_column=Column(Integer, nullable=True))
    status: MatchStatus = Field(
        sa_column=Column(
            SQLEnum(MatchStatus), nullable=False, default=MatchStatus.CREATED
        )
    )
    start_time: datetime = Field(
        sa_column=Column(DateTime, default=datetime.utcnow, nullable=False)
    )
    end_time: datetime = Field(sa_column=Column(DateTime, nullable=True))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
