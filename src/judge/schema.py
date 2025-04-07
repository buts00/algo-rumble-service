import uuid

from pydantic import BaseModel
from typing import Optional


class SubmissionRequest(BaseModel):
    source_code: str
    language_id: int
    stdin: Optional[str] = ""
    expected_output: Optional[str] = ""
    redirect_stderr_to_stdout: bool = True


class SubmissionResponse(BaseModel):
    token: str
    message: str


class CodeSubmission(BaseModel):
    source_code: str
    language_id: int = 71
    problem_id: uuid.UUID | None = None
