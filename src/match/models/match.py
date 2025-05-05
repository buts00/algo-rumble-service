import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
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

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID_TYPE, nullable=False, primary_key=True, default=uuid.uuid4, index=True
        ),
    )
    player1_id: uuid.UUID = Field(sa_column=Column(UUID_TYPE, nullable=False))
    player2_id: uuid.UUID = Field(sa_column=Column(UUID_TYPE, nullable=False))
    winner_id: uuid.UUID = Field(sa_column=Column(UUID_TYPE, nullable=True))
    problem_id: uuid.UUID = Field(sa_column=Column(UUID_TYPE, nullable=True))
    status: MatchStatus = Field(
        sa_column=Column(
            SQLEnum(MatchStatus), nullable=False, default=MatchStatus.CREATED
        )
    )
    player1_accepted: bool = Field(default=False)
    player2_accepted: bool = Field(default=False)
    start_time: datetime = Field(
        sa_column=Column(DateTime, default=datetime.utcnow, nullable=False)
    )
    end_time: datetime = Field(sa_column=Column(DateTime, nullable=True))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
