from datetime import datetime
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Column, Field, SQLModel


class BaseModel(SQLModel):
    """Abstract base model for database entities with common fields."""

    __abstract__ = True

    id: UUID4 = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
            default=UUID4,
        ),
        description="Unique identifier of the entity.",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the entity was created.",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the entity was last updated.",
    )