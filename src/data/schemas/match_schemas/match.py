import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.data.schemas import MatchStatus


class MatchBase(BaseModel):
    player1_id: uuid.UUID
    player2_id: uuid.UUID
    problem_id: Optional[int] = None
    status: MatchStatus = MatchStatus.CREATED


class MatchCreate(MatchBase):
    pass


class MatchResponse(MatchBase):
    id: int
    winner_id: Optional[uuid.UUID] = None
    start_time: datetime
    end_time: Optional[datetime] = None

    model_config = {"from_attributes": True}