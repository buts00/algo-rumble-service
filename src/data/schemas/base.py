import os
import uuid
from datetime import datetime

from sqlalchemy import String, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as pg_UUID
from sqlmodel import Column, Field, SQLModel


# Custom UUID type for SQLite compatibility
class UUIDType(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


# Use a different column type for UUID in tests (SQLite compatibility)
if os.environ.get("TESTING") == "True":
    UUID_TYPE = UUIDType
else:
    UUID_TYPE = pg_UUID


class BaseModel(SQLModel):
    __abstract__ = True

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID_TYPE,
            nullable=False,
            primary_key=True,
            default=uuid.uuid4,
        )
    )

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)