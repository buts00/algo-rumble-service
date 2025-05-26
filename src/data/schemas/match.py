from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import UUID4
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy import Enum as SQLEnum
from sqlmodel import Field, SQLModel
from src.data.schemas.base import BaseModel


class MatchStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class MatchBase(BaseModel):
    player1_id: UUID4
    player2_id: UUID4
    problem_id: Optional[UUID4] = None
    status: MatchStatus = MatchStatus.CREATED


class FindMatchRequest(SQLModel):
    user_id: str


class AcceptMatchRequest(SQLModel):
    user_id: str
    match_id: str


class Match(BaseModel, table=True):
    __tablename__ = "matches"

    player1_id: UUID4 = Field(sa_column=Column(SA_UUID(as_uuid=True), nullable=False))
    player2_id: UUID4 = Field(sa_column=Column(SA_UUID(as_uuid=True), nullable=False))
    winner_id: Optional[UUID4] = Field(
        sa_column=Column(SA_UUID(as_uuid=True), nullable=True)
    )
    problem_id: Optional[UUID4] = Field(
        sa_column=Column(SA_UUID(as_uuid=True), nullable=True)
    )
    status: MatchStatus = Field(
        sa_column=Column(
            SQLEnum(MatchStatus), nullable=False, default=MatchStatus.CREATED
        )
    )
    player1_accepted: bool = Field(default=False)
    player2_accepted: bool = Field(default=False)
    player1_old_rating: Optional[int] = Field(default=None, nullable=True)
    player2_old_rating: Optional[int] = Field(default=None, nullable=True)
    player1_new_rating: Optional[int] = Field(default=None, nullable=True)
    player2_new_rating: Optional[int] = Field(default=None, nullable=True)
    start_time: datetime = Field(
        sa_column=Column(DateTime, default=datetime.utcnow, nullable=False)
    )
    end_time: Optional[datetime] = Field(sa_column=Column(DateTime, nullable=True))


class MatchCreate(MatchBase):
    pass


class MatchResponse(MatchBase):
    id: UUID4
    winner_id: Optional[UUID4] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    model_config = {"from_attributes": True}


class CapitulateRequest(BaseModel):
    match_id: UUID4
    loser_id: UUID4


class PlayerQueueEntry(BaseModel):
    user_id: UUID4
    rating: int
    timestamp: datetime = datetime.utcnow()

    class Config:
        json_encoders = {
            UUID4: str,  # Automatically convert UUID to string in JSON
            datetime: lambda v: v.isoformat(),  # Convert datetime to ISO format
        }


class MatchQueueResult(BaseModel):
    success: bool
    message: str
    match_id: Optional[UUID4] = None
