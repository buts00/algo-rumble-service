import os

from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

# Import models to ensure they're registered with SQLModel.metadata
# These imports are needed even though they're not directly used
from src.auth.model import User  # noqa: F401
from src.match.models.match import Match  # noqa: F401

# Set environment variable to indicate we're running tests
os.environ["TESTING"] = "True"

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# Create test engine with in-memory SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Create tables
SQLModel.metadata.create_all(bind=engine)

print("Database tables created successfully:")
for table in SQLModel.metadata.tables:
    print(f"- {table}")

# Check if tables exist

inspector = inspect(engine)
tables = inspector.get_table_names()
print("\nTables in database:")
for table in tables:
    print(f"- {table}")
