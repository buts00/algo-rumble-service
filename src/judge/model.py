from sqlmodel import Field
from datetime import datetime
import uuid

from src.db.model import BaseModel


class UserSubmission(BaseModel, table=True):
    __tablename__ = "user_submissions"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    submission_token: str = Field(max_length=255, index=True)
    problem_id: int | None
    created_at: datetime = Field(default_factory=datetime.now)
