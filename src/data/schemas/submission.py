from uuid import UUID

from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    user_id: UUID
    match_id: UUID
    code: str
    language: str
