from typing import List
from sqlalchemy import ARRAY, Column, String
from sqlmodel import Field
from src.storage.models.base import BaseModel


class Problem(BaseModel, table=True):
    """
    Represents a coding problem in the system.
    Problems are stored in a Digital Ocean bucket, and this model
    contains metadata about the problems.
    """

    __tablename__ = "problems"

    rating: int = Field(nullable=False)
    topics: List[str] = Field(sa_column=Column(ARRAY(String), nullable=False))
    bucket_path: str = Field(sa_column=Column(String, nullable=True))
