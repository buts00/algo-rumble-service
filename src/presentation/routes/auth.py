from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.business.services import (AccessTokenFromCookie,
                                   RefreshTokenFromCookie, UserService,
                                   create_access_token, create_refresh_token,
                                   get_user_service, verify_password)
from src.config import Config, logger
from src.data.repositories import RedisClient, get_redis_client, get_session
from src.data.schemas import UserCreateModel, UserLoginModel, UserResponseModel
from src.errors import AuthenticationException, AuthorizationException

auth_logger = logger.getChild("auth")
auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post(
    "/register",
    response_model=UserResponseModel,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account, generates access and refresh tokens, and sets them as HTTP-only cookies.",
)
async def create_user(
    user_data: UserCreateModel,
    response: Response,
    user_service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_session),
):
    auth_logger.info(f"Registration attempt for username: {user_data.username}")
    user_exists = await user_service.get_user_by_username(user_data.username, session)
    if user_exists:
        auth_logger.warning(f"Username already exists: {user_data.username}")
        raise AuthorizationException(detail="User with this username already exists")

    new_user = await user_service.create_user(user_data, session)
    access_token, refresh_token = generate_tokens_for_user(new_user)
    await user_service.update_refresh_token(new_user.id, refresh_token, session)
    set_auth_cookies(response, access_token, refresh_token)
    auth_logger.info(f"User registered: {new_user.username} (ID: {new_user.id})")
    return new_user


@auth_router.post(
    "/login",
    response_model=UserResponseModel,
    summary="Log in a user",
    description="Authenticates a user, generates access and refresh tokens, and sets them as HTTP-only cookies.",
)
async def login(
    login_data: UserLoginModel,
    response: Response,
    user_service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_session),
):
    auth_logger.info(f"Login attempt for username: {login_data.username}")
    user = await user_service.get_user_by_username(login_data.username, session)
    if not user or not verify_password(login_data.password, user.password_hash):
        auth_logger.warning(f"Invalid credentials for username: {login_data.username}")
        raise AuthenticationException(detail="Invalid credentials")

    access_token, refresh_token = generate_tokens_for_user(user)
    await user_service.update_refresh_token(user.id, refresh_token, session)
    set_auth_cookies(response, access_token, refresh_token)
    auth_logger.info(f"User logged in: {user.username} (ID: {user.id})")
    return user


@auth_router.get(
    "/refresh",
    summary="Refresh JWT tokens",
    description="Refreshes access and refresh tokens using the refresh token cookie, adding the old token to a Redis blocklist.",
)
async def update_tokens(
    response: Response,
    token_details: dict = Depends(RefreshTokenFromCookie()),
    user_service: UserService = Depends(get_user_service),
    redis_client: RedisClient = Depends(get_redis_client),
    session: AsyncSession = Depends(get_session),
):
    user_id = token_details["user"]["id"]
    auth_logger.info(f"Token refresh attempt for user ID: {user_id}")
    user = await user_service.get_user_by_id(user_id, session)
    if not user:
        auth_logger.warning(f"User not found: ID {user_id}")
        raise AuthenticationException(detail="Invalid credentials")

    await redis_client.add_jti_to_blocklist(token_details["jti"])
    access_token, refresh_token = generate_tokens_for_user(user)
    await user_service.update_refresh_token(user.id, refresh_token, session)
    set_auth_cookies(response, access_token, refresh_token)
    auth_logger.info(f"Tokens refreshed for user: {user.username} (ID: {user.id})")
    return {"message": "Tokens refreshed"}


@auth_router.get(
    "/me",
    response_model=UserResponseModel,
    summary="Get current user",
    description="Returns the data of the currently authenticated user based on the access token.",
)
async def get_current_user(
    user_service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_session),
    token_data: dict = Depends(AccessTokenFromCookie()),
):
    user_id = token_data["user"]["id"]
    auth_logger.debug(f"Fetching data for user ID: {user_id}")
    user = await user_service.get_user_by_id(user_id, session)
    if not user:
        auth_logger.warning(f"User not found: ID {user_id}")
        raise AuthenticationException(detail="User not found")
    return user


@auth_router.get(
    "/logout",
    summary="Log out a user",
    description="Adds access and refresh tokens to a Redis blocklist and deletes the cookies.",
    response_model=None,  # Add this
)
async def revoke_token(
    response: Response,
    refresh_token_details: dict = Depends(RefreshTokenFromCookie()),
    access_token_details: dict = Depends(AccessTokenFromCookie()),
    redis_client: RedisClient = Depends(get_redis_client),
):
    user_id = refresh_token_details["user"]["id"]
    auth_logger.info(f"Logout attempt for user ID: {user_id}")
    await redis_client.add_jti_to_blocklist(refresh_token_details["jti"])
    await redis_client.add_jti_to_blocklist(access_token_details["jti"])
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(
        key="access_token", httponly=True, secure=True, samesite="strict"
    )
    response.delete_cookie(
        key="refresh_token", httponly=True, secure=True, samesite="strict"
    )
    auth_logger.info(f"User logged out: ID {user_id}")
    return response


def generate_tokens_for_user(user) -> tuple[str, str]:
    access_token = create_access_token(
        {"id": str(user.id), "username": user.username}
    )
    refresh_token = create_refresh_token(
        {"id": str(user.id), "username": user.username}
    )
    return access_token, refresh_token

@auth_router.get(
    "/refresh",
    summary="Refresh JWT tokens",
    description="Refreshes access and refresh tokens using the refresh token cookie, adding the old token to a Redis blocklist.",
    response_model=None,  # Disable response model generation
)
async def update_tokens(
    response: Response,
    token_details: dict = Depends(RefreshTokenFromCookie()),
    user_service: UserService = Depends(get_user_service),
    redis_client: RedisClient = Depends(get_redis_client),
    session: AsyncSession = Depends(get_session),
):
    user_id = token_details["user"]["id"]
    username = token_details["user"].get("username", "unknown")
    auth_logger.info(f"Token refresh attempt for user ID: {user_id}")
    user = await user_service.get_user_by_id(user_id, session)
    if not user:
        auth_logger.warning(f"User not found: ID {user_id}")
        raise AuthenticationException(detail="Invalid credentials")

    await redis_client.add_jti_to_blocklist(token_details["jti"])
    access_token, refresh_token = generate_tokens_for_user(user)
    await user_service.update_refresh_token(user.id, refresh_token, session)
    set_auth_cookies(response, access_token, refresh_token)
    auth_logger.info(f"Tokens refreshed for user: {user.username} (ID: {user.id})")
    return {"message": "Tokens refreshed"}

def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=Config.JWT_ACCESS_TOKEN_EXPIRY,
        httponly=True,
        secure=True,
        samesite="none",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=Config.JWT_REFRESH_TOKEN_EXPIRY,
        httponly=True,
        secure=True,
        samesite="none",
    )
