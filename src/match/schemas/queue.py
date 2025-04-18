from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PlayerQueueEntry(BaseModel):
    """
    Represents a player in the match queue.
    """

    user_id: int
    rating: int
    timestamp: datetime = datetime.utcnow()


class MatchQueueResult(BaseModel):
    """
    Represents the result of a match queue operation.
    """

    success: bool
    message: str
    match_id: Optional[int] = None
