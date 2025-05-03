from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, ARRAY
from sqlmodel import Field, SQLModel

class Problem(SQLModel, table=True):
    """
    Represents a coding problem in the system.
    Problems are stored in a Digital Ocean bucket, and this model
    contains metadata about the problems.
    """
    __tablename__ = "problems"

    id: int = Field(primary_key=True, index=True)
    rating: int = Field(sa_column=Column(Integer, nullable=False))
    topics: List[str] = Field(sa_column=Column(ARRAY(String), nullable=False))
    
    # Additional metadata fields
    title: str = Field(sa_column=Column(String, nullable=False))
    description: Optional[str] = Field(sa_column=Column(String, nullable=True))
    difficulty: Optional[str] = Field(sa_column=Column(String, nullable=True))
    
    # Path to the problem in the Digital Ocean bucket
    bucket_path: str = Field(sa_column=Column(String, nullable=False))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)