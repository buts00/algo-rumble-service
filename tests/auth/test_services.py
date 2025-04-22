import pytest

from src.auth.model import User
from src.auth.schemas import UserCreateModel
from src.auth.service import UserService
from src.auth.util import get_password_hash, verify_password


@pytest.mark.asyncio
async def test_create_user(test_db):
    # Test data
    user_data = UserCreateModel(
        username="testuser", password="password123", country_code="US"
    )

    # Call function
    user = await UserService.create_user(user_data, test_db)

    # Assertions
    assert user is not None
    assert user.username == user_data.username
    assert user.country_code == user_data.country_code
    assert user.password_hash is not None
    assert verify_password(
        "password123", user.password_hash
    )  # Verify password is hashed correctly


@pytest.mark.asyncio
async def test_authenticate_user_success(test_db):
    # Create a test user with known password
    user = User(
        username="authuser",
        password_hash=get_password_hash("correctpass"),
        country_code="US",
    )
    test_db.add(user)
    test_db.commit()

    # Call function with correct password
    authenticated_user = await UserService.get_user_by_username("authuser", test_db)

    # Assertions
    assert authenticated_user is not None
    assert authenticated_user.username == "authuser"


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(test_db):
    # Create a test user with known password
    user = User(
        username="authuser",
        password_hash=get_password_hash("correctpass"),
        country_code="US",
    )
    test_db.add(user)
    test_db.commit()

    # Call function with wrong password
    authenticated_user = await UserService.get_user_by_username("authuser", test_db)

    # Assertions
    assert authenticated_user is not None
    assert not verify_password("wrongpass", authenticated_user.password_hash)


@pytest.mark.asyncio
async def test_get_user_by_username_exists(test_db):
    # Create a test user
    user = User(username="findme", password_hash="hash", country_code="US")
    test_db.add(user)
    test_db.commit()

    # Call function
    found_user = await UserService.get_user_by_username("findme", test_db)

    # Assertions
    assert found_user is not None
    assert found_user.username == "findme"


@pytest.mark.asyncio
async def test_get_user_by_username_not_exists(test_db):
    # Call function with non-existent username
    found_user = await UserService.get_user_by_username("nonexistent", test_db)

    # Assertions
    assert found_user is None


@pytest.mark.asyncio
async def test_get_user_by_id_exists(test_db):
    # Create a test user
    user = User(username="iduser", password_hash="hash", country_code="US")
    test_db.add(user)
    test_db.commit()

    # Call function
    found_user = await UserService.get_user_by_id(user.id, test_db)

    # Assertions
    assert found_user is not None
    assert found_user.id == user.id


@pytest.mark.asyncio
async def test_get_user_by_id_not_exists(test_db):
    # Call function with non-existent ID
    found_user = await UserService.get_user_by_id(999, test_db)

    # Assertions
    assert found_user is None


@pytest.mark.asyncio
async def test_update_user_refresh_token(test_db):
    # Create a test user
    user = User(username="tokenuser", password_hash="hash", country_code="US")
    test_db.add(user)
    test_db.commit()

    # Call function
    new_token = "new_refresh_token"
    await UserService.update_refresh_token(user.id, new_token, test_db)

    # Fetch updated user
    updated_user = await UserService.get_user_by_id(user.id, test_db)

    # Assertions
    assert updated_user is not None
    assert updated_user.refresh_token == new_token
