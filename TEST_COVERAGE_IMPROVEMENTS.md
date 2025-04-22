# Test Coverage Improvements for Algo Rumble

Currently, the test coverage is at 67%. Here are suggestions to improve it:

## 1. Service Layer Tests

### Auth Service Tests (`tests/auth/test_services.py`)

```python
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from src.auth.service import (
    create_user,
    authenticate_user,
    get_user_by_username,
    get_user_by_id,
    update_user_refresh_token,
)
from src.auth.model import User

def test_create_user(test_db):
    # Test data
    username = "testuser"
    password = "password123"
    country_code = "US"
    
    # Call function
    user = create_user(test_db, username, password, country_code)
    
    # Assertions
    assert user is not None
    assert user.username == username
    assert user.country_code == country_code
    assert user.password_hash is not None
    assert user.password_hash != password  # Password should be hashed

def test_authenticate_user_success(test_db):
    # Create a test user with known password
    from src.auth.util import get_password_hash
    user = User(
        username="authuser",
        password_hash=get_password_hash("correctpass"),
        country_code="US"
    )
    test_db.add(user)
    test_db.commit()
    
    # Call function with correct password
    authenticated_user = authenticate_user(test_db, "authuser", "correctpass")
    
    # Assertions
    assert authenticated_user is not None
    assert authenticated_user.username == "authuser"

def test_authenticate_user_wrong_password(test_db):
    # Create a test user with known password
    from src.auth.util import get_password_hash
    user = User(
        username="authuser",
        password_hash=get_password_hash("correctpass"),
        country_code="US"
    )
    test_db.add(user)
    test_db.commit()
    
    # Call function with wrong password
    authenticated_user = authenticate_user(test_db, "authuser", "wrongpass")
    
    # Assertions
    assert authenticated_user is None

def test_get_user_by_username_exists(test_db):
    # Create a test user
    user = User(username="findme", password_hash="hash", country_code="US")
    test_db.add(user)
    test_db.commit()
    
    # Call function
    found_user = get_user_by_username(test_db, "findme")
    
    # Assertions
    assert found_user is not None
    assert found_user.username == "findme"

def test_get_user_by_username_not_exists(test_db):
    # Call function with non-existent username
    found_user = get_user_by_username(test_db, "nonexistent")
    
    # Assertions
    assert found_user is None

def test_get_user_by_id_exists(test_db):
    # Create a test user
    user = User(username="iduser", password_hash="hash", country_code="US")
    test_db.add(user)
    test_db.commit()
    
    # Call function
    found_user = get_user_by_id(test_db, user.id)
    
    # Assertions
    assert found_user is not None
    assert found_user.id == user.id

def test_get_user_by_id_not_exists(test_db):
    # Call function with non-existent ID
    found_user = get_user_by_id(test_db, 999)
    
    # Assertions
    assert found_user is None

def test_update_user_refresh_token(test_db):
    # Create a test user
    user = User(username="tokenuser", password_hash="hash", country_code="US")
    test_db.add(user)
    test_db.commit()
    
    # Call function
    new_token = "new_refresh_token"
    updated_user = update_user_refresh_token(test_db, user.id, new_token)
    
    # Assertions
    assert updated_user is not None
    assert updated_user.refresh_token == new_token
```

### Match Service Tests (`tests/match/test_services.py`)

```python
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from src.match.service import (
    create_match,
    get_match_by_id,
    get_active_matches_for_user,
    update_match_status,
    check_user_in_match,
)
from src.match.models.match import Match, MatchStatus

def test_create_match(test_db):
    # Test data
    player1_id = 1
    player2_id = 2
    
    # Call function
    match = create_match(test_db, player1_id, player2_id)
    
    # Assertions
    assert match is not None
    assert match.player1_id == player1_id
    assert match.player2_id == player2_id
    assert match.status == MatchStatus.PENDING
    assert match.start_time is not None

def test_get_match_by_id_exists(test_db, test_match):
    match, _ = test_match
    
    # Call function
    found_match = get_match_by_id(test_db, match.id)
    
    # Assertions
    assert found_match is not None
    assert found_match.id == match.id

def test_get_match_by_id_not_exists(test_db):
    # Call function with non-existent ID
    found_match = get_match_by_id(test_db, 999)
    
    # Assertions
    assert found_match is None

def test_get_active_matches_for_user(test_db, test_match):
    match, _ = test_match
    
    # Update match to active status
    match.status = MatchStatus.ACTIVE
    test_db.commit()
    
    # Call function
    matches = get_active_matches_for_user(test_db, match.player1_id)
    
    # Assertions
    assert len(matches) == 1
    assert matches[0].id == match.id
    assert matches[0].status == MatchStatus.ACTIVE

def test_update_match_status(test_db, test_match):
    match, _ = test_match
    
    # Call function
    updated_match = update_match_status(test_db, match.id, MatchStatus.ACTIVE)
    
    # Assertions
    assert updated_match is not None
    assert updated_match.status == MatchStatus.ACTIVE

def test_check_user_in_match_true(test_db, test_match):
    match, _ = test_match
    
    # Call function for player1
    result = check_user_in_match(test_db, match.player1_id)
    
    # Assertions
    assert result is True

def test_check_user_in_match_false(test_db):
    # Call function for non-existent user
    result = check_user_in_match(test_db, 999)
    
    # Assertions
    assert result is False
```

## 2. WebSocket Tests

### WebSocket Tests (`tests/match/test_websocket.py`)

```python
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import WebSocket
from src.match.websocket import (
    websocket_endpoint,
    connected_users,
    notify_user,
)

@pytest.mark.asyncio
async def test_websocket_connection():
    # Mock WebSocket
    websocket = AsyncMock(spec=WebSocket)
    websocket.accept = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=["message", Exception("Test disconnect")])
    websocket.send_text = AsyncMock()
    
    # Mock user_id
    user_id = "123"
    
    # Call function (will raise exception to simulate disconnect)
    with pytest.raises(Exception, match="Test disconnect"):
        await websocket_endpoint(websocket, user_id)
    
    # Assertions
    websocket.accept.assert_called_once()
    assert user_id in connected_users
    
    # After exception, user should be removed from connected_users
    assert user_id not in connected_users

@pytest.mark.asyncio
async def test_notify_user_connected():
    # Mock WebSocket
    websocket = AsyncMock(spec=WebSocket)
    websocket.send_text = AsyncMock()
    
    # Add user to connected_users
    user_id = "123"
    connected_users[user_id] = websocket
    
    # Call function
    await notify_user(user_id, {"message": "test"})
    
    # Assertions
    websocket.send_text.assert_called_once()
    
    # Cleanup
    del connected_users[user_id]

@pytest.mark.asyncio
async def test_notify_user_not_connected():
    # Call function for non-connected user
    user_id = "456"
    
    # This should not raise an exception
    await notify_user(user_id, {"message": "test"})
```

## 3. Middleware Tests

### Rate Limit Middleware Tests (`tests/middleware/test_rate_limit.py`)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request, Response
from starlette.datastructures import Address
from src.middleware.rate_limit import RateLimitMiddleware

@pytest.mark.asyncio
async def test_rate_limit_middleware_allowed():
    # Mock Redis client
    redis_client = MagicMock()
    redis_client.get.return_value = "5"  # Below limit
    redis_client.exists.return_value = True
    
    # Create middleware
    middleware = RateLimitMiddleware(app=None, redis_client=redis_client)
    
    # Mock request
    request = MagicMock(spec=Request)
    request.client = Address(host="127.0.0.1", port=1234)
    request.url = MagicMock()
    request.url.path = "/api/v1/test"
    
    # Mock call_next
    async def mock_call_next(request):
        return Response(content="Test response")
    
    # Call middleware
    response = await middleware.dispatch(request, mock_call_next)
    
    # Assertions
    assert response.status_code != 429
    redis_client.incr.assert_called_once()

@pytest.mark.asyncio
async def test_rate_limit_middleware_exceeded():
    # Mock Redis client
    redis_client = MagicMock()
    redis_client.get.return_value = "100"  # At limit
    
    # Create middleware
    middleware = RateLimitMiddleware(app=None, redis_client=redis_client)
    middleware.rate_limit = 100  # Set limit
    
    # Mock request
    request = MagicMock(spec=Request)
    request.client = Address(host="127.0.0.1", port=1234)
    request.url = MagicMock()
    request.url.path = "/api/v1/test"
    
    # Mock call_next
    async def mock_call_next(request):
        return Response(content="Test response")
    
    # Call middleware
    response = await middleware.dispatch(request, mock_call_next)
    
    # Assertions
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.body.decode()

@pytest.mark.asyncio
async def test_rate_limit_middleware_docs_path():
    # Mock Redis client
    redis_client = MagicMock()
    
    # Create middleware
    middleware = RateLimitMiddleware(app=None, redis_client=redis_client)
    
    # Mock request to docs path
    request = MagicMock(spec=Request)
    request.url = MagicMock()
    request.url.path = "/docs"
    
    # Mock call_next
    async def mock_call_next(request):
        return Response(content="Docs response")
    
    # Call middleware
    response = await middleware.dispatch(request, mock_call_next)
    
    # Assertions
    assert response.status_code != 429
    # Redis functions should not be called for docs path
    redis_client.get.assert_not_called()
    redis_client.incr.assert_not_called()
```

## 4. Model and Schema Tests

### Auth Model Tests (`tests/auth/test_models.py`)

```python
import pytest
from src.auth.model import User

def test_user_model_creation():
    # Create a user
    user = User(
        username="testuser",
        password_hash="hashed_password",
        country_code="US",
        rating=1500
    )
    
    # Assertions
    assert user.username == "testuser"
    assert user.password_hash == "hashed_password"
    assert user.country_code == "US"
    assert user.rating == 1500
    assert user.refresh_token is None

def test_user_model_repr():
    # Create a user
    user = User(
        username="testuser",
        password_hash="hashed_password",
        country_code="US"
    )
    
    # Set ID (normally done by database)
    user.id = 1
    
    # Assertions
    assert str(user) == "User(id=1, username=testuser)"
```

### Match Model Tests (`tests/match/test_models.py`)

```python
import pytest
from datetime import datetime
from src.match.models.match import Match, MatchStatus

def test_match_model_creation():
    # Create a match
    match = Match(
        player1_id=1,
        player2_id=2,
        status=MatchStatus.PENDING,
        start_time=datetime.utcnow()
    )
    
    # Assertions
    assert match.player1_id == 1
    assert match.player2_id == 2
    assert match.status == MatchStatus.PENDING
    assert match.start_time is not None
    assert match.end_time is None

def test_match_model_repr():
    # Create a match
    match = Match(
        player1_id=1,
        player2_id=2,
        status=MatchStatus.PENDING
    )
    
    # Set ID (normally done by database)
    match.id = 1
    
    # Assertions
    assert str(match) == "Match(id=1, player1=1 vs player2=2, status=pending)"
```

## Implementation Strategy

To improve test coverage:

1. Start by implementing the service layer tests, as they test the core business logic
2. Then implement the WebSocket tests to cover real-time functionality
3. Add middleware tests to ensure rate limiting works correctly
4. Finally, add model and schema tests for completeness

This approach should significantly increase the test coverage from the current 67% to a much higher percentage.