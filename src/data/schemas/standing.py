from pydantic import BaseModel, UUID4
from typing import List


class StandingEntry(BaseModel):
    """Schema for a single entry in the standing."""

    id: UUID4
    username: str
    rating: int
    country_code: str

    model_config = {"from_attributes": True}


class StandingResponse(BaseModel):
    """Schema for the standing response."""

    users: List[StandingEntry]
    total: int
