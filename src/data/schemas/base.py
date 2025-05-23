from datetime import datetime
from pydantic import UUID4
from sqlmodel import Column, Field, SQLModel
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy import DateTime
import uuid

from datetime import datetime
from pydantic import UUID4
from sqlmodel import Field, SQLModel
import uuid

class BaseModel(SQLModel, table=False):
    """Abstract base model for database entities with common fields."""

    id: UUID4 = Field(default_factory=uuid.uuid4, primary_key=True, description="Unique identifier of the entity.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the entity was created.")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the entity was last updated.")