from pydantic import UUID4

from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    user_id: UUID4
    match_id: UUID4
    code: str
    language: str
