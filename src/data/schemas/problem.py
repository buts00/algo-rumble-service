import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import ARRAY, JSON, Column, String
from sqlmodel import Field, SQLModel

from src.data.schemas.base import UUID_TYPE


class Problem(SQLModel, table=True):
    """
    Represents a coding problem in the system.
    Problems are stored in a Digital Ocean bucket, and this model
    contains metadata about the problems.
    """

    __tablename__ = "problems"

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID_TYPE, nullable=False, primary_key=True, default=uuid.uuid4, index=True
        )
    )

    rating: int = Field(nullable=False)
    topics: List[str] = Field(sa_column=Column(ARRAY(String), nullable=False))

    # Path to the problem in the Digital Ocean bucket
    bucket_path: str = Field(sa_column=Column(String, nullable=True))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)