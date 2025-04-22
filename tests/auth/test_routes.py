from fastapi import status

from src.auth.model import User
from src.auth.util import create_access_token, create_refresh_token


# Test user registration
def test_register_success(client, test_db):
    # Test data
    user_data = {"username": "newuser", "password": "password123", "country_code": "US"}

    # Make request
    response = client.post("/api/v1/auth/register", json=user_data)

    # Check response
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["username"] == user_data["username"]
    assert "id" in data

    # Check cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    # Check database
    user = test_db.query(User).filter(User.username == user_data["username"]).first()
    assert user is not None
    assert user.username == user_data["username"]
    assert user.country_code == user_data["country_code"]


def test_register_existing_user(client, test_user):
    # Test data
    user_data = {
        "username": test_user.username,  # Use existing username
        "password": "password123",
        "country_code": "US",
    }

    # Make request
    response = client.post("/api/v1/auth/register", json=user_data)

    # Check response
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "already exists" in response.json()["detail"]


# Test user login
def test_login_success(client, test_user, test_db):
    # Update test user with a known password hash
    from src.auth.util import get_password_hash

    test_user.password_hash = get_password_hash("password123")
    test_db.commit()

    # Test data
    login_data = {"username": test_user.username, "password": "password123"}

    # Make request
    response = client.post("/api/v1/auth/login", json=login_data)

    # Check response
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == test_user.username
    assert data["id"] == str(test_user.id)

    # Check cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


def test_login_invalid_credentials(client, test_user, test_db):
    # Update test user with a known password hash
    from src.auth.util import get_password_hash

    test_user.password_hash = get_password_hash("password123")
    test_db.commit()

    # Test data
    login_data = {"username": test_user.username, "password": "wrongpassword"}

    # Make request
    response = client.post("/api/v1/auth/login", json=login_data)

    # Check response
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in response.json()["detail"]


# Test token refresh
def test_refresh_token_success(mock_redis, client, test_user, test_db):
    # mock_redis is provided by the fixture in conftest.py

    # Create tokens
    access_token = create_access_token(
        {"id": str(test_user.id), "username": test_user.username}
    )
    refresh_token = create_refresh_token(
        {"id": str(test_user.id), "username": test_user.username}
    )

    # Update user with refresh token
    test_user.refresh_token = refresh_token
    test_db.commit()

    # Set cookies on the client instance
    client.cookies.set("access_token", access_token)
    client.cookies.set("refresh_token", refresh_token)

    # Make request
    response = client.get("/api/v1/auth/refresh-token")

    # Check response
    assert response.status_code == status.HTTP_200_OK

    # Check cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    # Check redis blocklist
    mock_redis.return_value.add_jti_to_blocklist.assert_called_once()


# Test logout
def test_logout_success(mock_redis, client, test_user):
    # mock_redis is provided by the fixture in conftest.py

    # Create tokens
    access_token = create_access_token(
        {"id": str(test_user.id), "username": test_user.username}
    )
    refresh_token = create_refresh_token(
        {"id": str(test_user.id), "username": test_user.username}
    )

    # Set cookies on the client instance
    client.cookies.set("access_token", access_token)
    client.cookies.set("refresh_token", refresh_token)

    # Make request
    response = client.get("/api/v1/auth/logout")

    # Check response
    assert response.status_code == status.HTTP_200_OK
    assert "logged out successfully" in response.json()["message"]

    # Check cookies are deleted
    assert "access_token" not in response.cookies
    assert "refresh_token" not in response.cookies

    # Check redis blocklist
    assert (
        mock_redis.return_value.add_jti_to_blocklist.call_count == 2
    )  # Both tokens should be blocklisted
