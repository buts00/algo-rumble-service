from datetime import datetime
from typing import Optional
from pydantic import BaseModel, UUID4
from src.storage.models.match import MatchBase


class FindMatchRequest(BaseModel):
    user_id: str


class AcceptMatchRequest(BaseModel):
    user_id: str
    match_id: str


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
