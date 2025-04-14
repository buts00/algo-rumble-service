from sqlmodel import SQLModel, Field, Column
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID as pg_UUID


class BaseModel(SQLModel):
    __abstract__ = True

    id: uuid.UUID = Field(
        sa_column=Column(
            pg_UUID,
            nullable=False,
            primary_key=True,
            default=uuid.uuid4,
        )
    )

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
