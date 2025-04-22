# Set environment variable to indicate we're running tests
import os

os.environ["TESTING"] = "True"

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from src.auth.model import User, UserRole
from src.config import logger
from src.db.main import get_session
from src.main import app
from src.match.models.match import Match, MatchStatus

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# Create test engine with in-memory SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Create test session
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# We use SQLModel for models


# Override the get_session dependency
@pytest.fixture
def override_get_session():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Create test client
@pytest.fixture
def client(override_get_session, mock_redis):
    # Override the get_session dependency
    app.dependency_overrides[get_session] = lambda: override_get_session

    # Override the get_redis_client dependency
    from src.db.dependency import get_redis_client

    app.dependency_overrides[get_redis_client] = lambda: mock_redis.return_value

    # Create test client
    with TestClient(app) as test_client:
        yield test_client

    # Remove the override after the test
    app.dependency_overrides.clear()


# Create test database and tables
@pytest.fixture(scope="function")
def test_db():
    # Create tables
    SQLModel.metadata.create_all(bind=engine)

    # Provide the session
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()

        # Drop tables after test
        SQLModel.metadata.drop_all(bind=engine)


# Create a test user
@pytest.fixture
def test_user(test_db):
    user = User(
        username="testuser",
        password_hash="hashed_password",  # In a real test, use a proper hash
        role=UserRole.USER,
        rating=1000,
        country_code="US",
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# Create a test match
@pytest.fixture
def test_match(test_db, test_user):
    # Create another user for the match
    opponent = User(
        username="opponent",
        password_hash="hashed_password",
        role=UserRole.USER,
        rating=1000,
        country_code="UK",
    )
    test_db.add(opponent)
    test_db.commit()
    test_db.refresh(opponent)

    # Create a match between the users
    match = Match(
        player1_id=test_user.id, player2_id=opponent.id, status=MatchStatus.PENDING
    )
    test_db.add(match)
    test_db.commit()
    test_db.refresh(match)

    return match, opponent


# Mock Redis client for tests (autouse to ensure it's always applied)
@pytest.fixture(autouse=True)
def mock_redis():
    # Create a mock instance with the necessary methods
    redis_instance = MagicMock()
    redis_instance.get.return_value = None
    redis_instance.set.return_value = True
    redis_instance.delete.return_value = True
    redis_instance.exists.return_value = False
    redis_instance.incr.return_value = 1
    redis_instance.add_jti_to_blocklist.return_value = True
    redis_instance.token_in_blocklist.return_value = False

    # Patch the RedisClient class and its instance methods
    with patch("src.db.redis.RedisClient") as redis_mock:
        # Make the mock return the mock instance when instantiated
        redis_mock.return_value = redis_instance
        yield redis_mock


# Disable logging during tests
@pytest.fixture(autouse=True)
def disable_logging():
    logger.disabled = True
    yield
    logger.disabled = False
