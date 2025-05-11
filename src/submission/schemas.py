from pydantic import BaseModel
from uuid import UUID


class SubmissionCreate(BaseModel):
    user_id: UUID
    match_id: UUID
    code: str
    language: str