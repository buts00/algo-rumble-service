from datetime import datetime
from typing import Optional

from pydantic import UUID4, BaseModel


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