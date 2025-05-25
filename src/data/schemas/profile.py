from datetime import datetime
from pydantic import BaseModel


class MatchHistoryEntry(BaseModel):
    """Schema for a match history entry in a user's profile."""

    enemy_name: str
    status: str  # "win" or "loss"
    old_rating: int
    new_rating: int
    finished_at: datetime
