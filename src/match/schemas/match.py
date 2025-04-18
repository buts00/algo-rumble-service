from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from ...match.models.match import MatchStatus


class MatchBase(BaseModel):
    player1_id: int
    player2_id: int
    problem_id: Optional[int] = None
    status: MatchStatus = MatchStatus.CREATED


class MatchCreate(MatchBase):
    pass


class MatchResponse(MatchBase):
    id: int
    winner_id: Optional[int] = None
    start_time: datetime
    end_time: Optional[datetime] = None

    class Config:
        orm_mode = True
