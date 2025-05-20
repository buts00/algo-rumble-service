import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import ARRAY, Column, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class Problem(SQLModel, table=True):
    """
    Represents a coding problem in the system.
    Problems are stored in a Digital Ocean bucket, and this model
    contains metadata about the problems.
    """

    __tablename__ = "problems"

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID, nullable=False, primary_key=True, default=uuid.uuid4, index=True
        )
    )

    rating: int = Field(nullable=False)
    topics: List[str] = Field(sa_column=Column(ARRAY(String), nullable=False))

    # Path to the problem in the Digital Ocean bucket
    bucket_path: str = Field(sa_column=Column(String, nullable=True))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ProblemExample(BaseModel):
    """Schema for a problem example"""

    input: str
    output: str
    explanation: Optional[str] = None


class ProblemDetail(BaseModel):
    """Schema for problem details"""

    name: str
    description: str
    time_limit: str
    memory_limit: str
    input_description: str
    output_description: str
    examples: List[ProblemExample]
    constraints: List[str]
    note: Optional[str] = None


class ProblemBase(BaseModel):
    """Base schema for Problem with common attributes"""

    rating: int
    topics: List[str]


class ProblemCreate(ProblemBase):
    """Schema for creating a new problem"""

    problem: ProblemDetail


class ProblemUpdate(BaseModel):
    """Schema for updating an existing problem"""

    rating: Optional[int] = None
    topics: Optional[List[str]] = None
    problem: Optional[ProblemDetail] = None


class ProblemResponse(ProblemBase):
    """Schema for problem responses"""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    problem: Optional[ProblemDetail] = None

    class Config:
        from_attributes = True


class ProblemSelectionParams(BaseModel):
    """Parameters for selecting a problem for a match"""

    player1_rating: int
    player2_rating: int
    preferred_topics: Optional[List[str]] = None
    exclude_problem_ids: Optional[List[uuid.UUID]] = None
