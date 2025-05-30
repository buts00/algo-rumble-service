from datetime import datetime
from typing import List

from pydantic import BaseModel


class MatchHistoryEntry(BaseModel):
    """Schema for a match history entry in a user's profile."""

    enemy_name: str
    status: str  # "win" or "loss"
    old_rating: int
    new_rating: int
    finished_at: datetime


class MatchHistory(BaseModel):
    """Schema for a match history in a user's profile."""

    entries: List[MatchHistoryEntry]
    total: int


class ContributionCalendarEntry(BaseModel):
    """Schema for a contribution calendar entry in a user's profile."""

    date: datetime
    count: int


class ContributionCalendar(BaseModel):
    """Schema for a contribution calendar in a user's profile."""

    entries: List[ContributionCalendarEntry]


class RatingHistoryEntry(BaseModel):
    """Schema for a rating history entry in a user's profile."""

    date: datetime
    rating: int


class RatingHistory(BaseModel):
    """Schema for a rating history in a user's profile."""

    history: List[RatingHistoryEntry]


class TopicStatEntry(BaseModel):
    """Schema for a topic statistics entry in a user's profile."""

    topic: str
    win_count: int


class TopicStats(BaseModel):
    """Schema for topic statistics in a user's profile."""

    topics: List[TopicStatEntry]
