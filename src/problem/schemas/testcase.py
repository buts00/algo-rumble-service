import uuid
from typing import List

from pydantic import BaseModel


class TestCase(BaseModel):
    """Schema for a test case"""

    in_data: str
    out_data: str


class TestCaseInput(BaseModel):
    """Schema for test case input in the request"""

    input: str
    output: str


class TestCaseCreate(BaseModel):
    """Schema for creating test cases for a problem"""

    problem_id: str
    testcases: List[TestCaseInput]


class TestCaseResponse(BaseModel):
    """Schema for test case response"""

    problem_id: uuid.UUID
    testcase_count: int
    success: bool
    message: str
