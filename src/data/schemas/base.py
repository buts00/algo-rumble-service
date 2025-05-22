from datetime import datetime
from pydantic import UUID4
from sqlmodel import Column, Field, SQLModel
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
import uuid

class BaseModel(SQLModel, table=False):
    """Abstract base model for database entities with common fields."""

    id: UUID4 = Field(
        sa_column=Column(
            SA_UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
            default=uuid.uuid4,
        ),
        description="Unique identifier of the entity.",
    )

    created_at: datetime = Field(
        sa_column=Column(
            default_factory=datetime.utcnow,
            nullable=False,
        ),
        description="Timestamp when the entity was created.",
    )

    updated_at: datetime = Field(
        sa_column=Column(
            default_factory=datetime.utcnow,
            nullable=False,
        ),
        description="Timestamp when the entity was last updated.",
    )