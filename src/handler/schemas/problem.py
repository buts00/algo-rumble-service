from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, UUID4


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
