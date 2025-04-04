from typing import Optional

from sqlmodel import SQLModel, Field
from datetime import datetime
import uuid


class UserSubmission(SQLModel, table=True):
    __tablename__ = "user_submissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.uid")
    submission_token: str = Field(max_length=255, index=True)
    problem_id: Optional[uuid.UUID] = None
    created_at: datetime = Field(default=datetime.now)
