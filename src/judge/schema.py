from datetime import datetime
import uuid
from pydantic import BaseModel
from typing import Optional, Dict, Any


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


class SubmissionBrief(BaseModel):
    submission_token: str
    status: Dict[str, Any]
    time: Optional[float]
    memory: Optional[float]
    created_at: datetime
    problem_id: Optional[uuid.UUID]
    language_id: int
    language_name: Optional[str]


class SubmissionDetail(BaseModel):
    source_code: str
    language_id: int
    language_name: str
    status: Dict[str, Any]
    stdin: str
    stdout: str
    stderr: str | None
    compile_output: str | None
    time: Optional[float]
    memory: Optional[float]
    created_at: datetime
    problem_id: Optional[uuid.UUID]
    exit_code: Optional[int]
    exit_signal: Optional[int]