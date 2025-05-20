import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import UUID4, BaseModel
from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class MatchStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class MatchBase(BaseModel):
    player1_id: uuid.UUID
    player2_id: uuid.UUID
    problem_id: Optional[int] = None
    status: MatchStatus = MatchStatus.CREATED


class FindMatchRequest(SQLModel):
    user_id: str


class AcceptMatchRequest(SQLModel):
    user_id: str
    match_id: str


class Match(SQLModel, table=True):
    __tablename__ = "matches"

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID, nullable=False, primary_key=True, default=uuid.uuid4, index=True
        ),
    )
    player1_id: uuid.UUID = Field(sa_column=Column(UUID, nullable=False))
    player2_id: uuid.UUID = Field(sa_column=Column(UUID, nullable=False))
    winner_id: uuid.UUID = Field(sa_column=Column(UUID, nullable=True))
    problem_id: uuid.UUID = Field(sa_column=Column(UUID, nullable=True))
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


class MatchCreate(MatchBase):
    pass


class MatchResponse(MatchBase):
    id: int
    winner_id: Optional[uuid.UUID] = None
    start_time: datetime
    end_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CapitulateRequest(BaseModel):
    match_id: uuid.UUID
    loser_id: uuid.UUID


class PlayerQueueEntry(BaseModel):

    user_id: UUID4
    rating: int
    timestamp: datetime = datetime.utcnow()


class MatchQueueResult(BaseModel):
    """
    Represents the result of a match queue operation.
    """

    success: bool
    message: str
    match_id: Optional[int] = None
