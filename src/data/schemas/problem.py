from datetime import datetime
from typing import List, Optional
from pydantic import UUID4
from sqlalchemy import ARRAY, Column, String
from sqlmodel import Field
from src.data.schemas.base import BaseModel


class Problem(BaseModel, table=True):
    """
    Represents a coding problem in the system.
    Problems are stored in a Digital Ocean bucket, and this model
    contains metadata about the problems.
    """

    __tablename__ = "problems"

    rating: int = Field(nullable=False)
    topics: List[str] = Field(sa_column=Column(ARRAY(String), nullable=False))
    bucket_path: str = Field(sa_column=Column(String, nullable=True))


class ProblemExample(BaseModel):
    input: str
    output: str
    explanation: Optional[str] = None


class ProblemDetail(BaseModel):
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
    rating: int
    topics: List[str]


class ProblemCreate(ProblemBase):
    problem: ProblemDetail


class ProblemUpdate(BaseModel):
    rating: Optional[int] = None
    topics: Optional[List[str]] = None
    problem: Optional[ProblemDetail] = None


class ProblemResponse(ProblemBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    problem: Optional[ProblemDetail] = None
    model_config = {"from_attributes": True}


class ProblemSelectionParams(BaseModel):
    player1_rating: int
    player2_rating: int
    preferred_topics: Optional[List[str]] = None
    exclude_problem_ids: Optional[List[UUID4]] = None
