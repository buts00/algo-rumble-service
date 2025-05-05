import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ProblemBase(BaseModel):
    """Base schema for Problem with common attributes"""

    rating: int
    topics: List[str]
    bucket_path: str


class ProblemCreate(ProblemBase):
    """Schema for creating a new problem"""

    pass


class ProblemUpdate(BaseModel):
    """Schema for updating an existing problem"""

    rating: Optional[int] = None
    topics: Optional[List[str]] = None
    bucket_path: Optional[str] = None


class ProblemResponse(ProblemBase):
    """Schema for problem responses"""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProblemSelectionParams(BaseModel):
    """Parameters for selecting a problem for a match"""

    player1_rating: int
    player2_rating: int
    preferred_topics: Optional[List[str]] = None
    exclude_problem_ids: Optional[List[uuid.UUID]] = None
