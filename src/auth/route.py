from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio.session import AsyncSession
from starlette.responses import JSONResponse

from src.config import Config, logger
from src.db.main import get_session
from src.errors import (
    AuthenticationException,
    AuthorizationException,
    DatabaseException,
)

from ..db.dependency import get_redis_client
from ..db.redis import RedisClient
from .dependency import AccessTokenFromCookie, RefreshTokenFromCookie, get_user_service
from .schemas import UserCreateModel, UserLoginModel, UserResponseModel
from .service import UserService
from .util import create_access_token, create_refresh_token, verify_password

auth_logger = logger.getChild("auth")

auth_router = APIRouter()


@auth_router.post(
    "/register", response_model=UserResponseModel, status_code=status.HTTP_201_CREATED
)
async def create_user(
    response: Response,
    user_data: UserCreateModel,
    user_service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    auth_logger.info(f"Registration attempt for username: {user_data.username}")

    try:
        user_exists = await user_service.get_user_by_username(
            user_data.username, session
        )

        if user_exists:
            auth_logger.warning(
                f"Registration failed: Username already exists: {user_data.username}"
            )
            raise AuthorizationException(
                detail="user with this username already exists"
            )

        try:
            new_user = await user_service.create_user(user_data, session)
            auth_logger.info(
                f"User created successfully: {new_user.username} (ID: {new_user.id})"
            )
        except SQLAlchemyError as db_error:
            auth_logger.error(f"Database error during user creation: {str(db_error)}")
            raise DatabaseException(
                detail="Failed to create user due to database error"
            )
        except Exception as e:
            auth_logger.error(f"Unexpected error during user creation: {str(e)}")
            raise

        access_token, refresh_token = generate_tokens_for_user(new_user)
        auth_logger.debug(f"Tokens generated for user: {new_user.username}")

        try:
            await user_service.update_refresh_token(new_user.id, refresh_token, session)
            auth_logger.debug(f"Refresh token updated for user: {new_user.username}")
        except SQLAlchemyError as db_error:
            auth_logger.error(
                f"Database error during refresh token update: {str(db_error)}"
            )
            raise DatabaseException(
                detail="Failed to update refresh token due to database error"
            )

        set_auth_cookies(response, access_token, refresh_token)
        auth_logger.info(
            f"User registered successfully: {new_user.username} (ID: {new_user.id})"
        )

        return new_user
    except (AuthorizationException, DatabaseException):
        raise
    except Exception as e:
        auth_logger.error(f"Unexpected error during user registration: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred during registration"
        )


@auth_router.post("/login", response_model=UserResponseModel)
async def login(
    response: Response,
    login_data: UserLoginModel,
    user_service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    auth_logger.info(f"Login attempt for username: {login_data.username}")

    try:
        try:
            user = await user_service.get_user_by_username(login_data.username, session)
        except SQLAlchemyError as db_error:
            auth_logger.error(f"Database error during user lookup: {str(db_error)}")
            raise DatabaseException(
                detail="Failed to retrieve user due to database error"
            )

        if not user:
            auth_logger.warning(f"Login failed: User not found: {login_data.username}")
            raise AuthenticationException(detail="Invalid credentials")

        if not verify_password(login_data.password, user.password_hash):
            auth_logger.warning(
                f"Login failed: Invalid password for user: {login_data.username}"
            )
            raise AuthenticationException(detail="Invalid credentials")

        auth_logger.info(
            f"User authenticated successfully: {user.username} (ID: {user.id})"
        )

        access_token, refresh_token = generate_tokens_for_user(user)
        auth_logger.debug(f"Tokens generated for user: {user.username}")

        try:
            await user_service.update_refresh_token(user.id, refresh_token, session)
            auth_logger.debug(f"Refresh token updated for user: {user.username}")
        except SQLAlchemyError as db_error:
            auth_logger.error(
                f"Database error during refresh token update: {str(db_error)}"
            )
            raise DatabaseException(
                detail="Failed to update refresh token due to database error"
            )

        set_auth_cookies(response, access_token, refresh_token)
        auth_logger.info(
            f"User logged in successfully: {user.username} (ID: {user.id})"
        )

        return user
    except (AuthenticationException, DatabaseException):
        # These exceptions will be handled by the global exception handlers
        raise
    except Exception as e:
        auth_logger.error(f"Unexpected error during login: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred during login")


@auth_router.get("/refresh-token")
async def update_tokens(
    response: Response,
    token_details: dict = Depends(RefreshTokenFromCookie()),
    user_service: UserService = Depends(get_user_service),
    redis_client: RedisClient = Depends(get_redis_client),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    user_id = token_details["user"]["id"]
    username = token_details["user"].get("username", "unknown")

    auth_logger.info(
        f"Token refresh attempt for user ID: {user_id}, username: {username}"
    )

    try:
        try:
            user = await user_service.get_user_by_id(user_id, session)
        except SQLAlchemyError as db_error:
            auth_logger.error(f"Database error during user lookup: {str(db_error)}")
            raise DatabaseException(
                detail="Failed to retrieve user due to database error"
            )

        if not user:
            auth_logger.warning(f"Token refresh failed: User not found: ID {user_id}")
            raise AuthenticationException(detail="Invalid credentials")

        # Add the old token to the blocklist
        try:
            jti = token_details["jti"]
            redis_client.add_jti_to_blocklist(jti)
            auth_logger.debug(f"Added token to blocklist: JTI {jti}")
        except Exception as redis_error:
            auth_logger.error(
                f"Redis error during token blocklisting: {str(redis_error)}"
            )
            # Continue even if blocklisting fails, as this is not critical

        # Generate new tokens
        access_token, refresh_token = generate_tokens_for_user(user)
        auth_logger.debug(f"New tokens generated for user: {user.username}")

        # Update the refresh token in the database
        try:
            await user_service.update_refresh_token(user.id, refresh_token, session)
            auth_logger.debug(f"Refresh token updated for user: {user.username}")
        except SQLAlchemyError as db_error:
            auth_logger.error(
                f"Database error during refresh token update: {str(db_error)}"
            )
            raise DatabaseException(
                detail="Failed to update refresh token due to database error"
            )

        # Set the new tokens as cookies
        set_auth_cookies(response, access_token, refresh_token)
        auth_logger.info(
            f"Tokens refreshed successfully for user: {user.username} (ID: {user.id})"
        )

        return {"Okay": "👍"}
    except (AuthenticationException, DatabaseException):
        # These exceptions will be handled by the global exception handlers
        raise
    except Exception as e:
        auth_logger.error(f"Unexpected error during token refresh: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred during token refresh"
        )


@auth_router.get("/me")
async def get_current_user(
    token_data=Depends(AccessTokenFromCookie()), request: Request = None
):
    user_id = token_data.get("user", {}).get("id", "unknown")
    username = token_data.get("user", {}).get("username", "unknown")

    auth_logger.debug(
        f"Current user data requested for user ID: {user_id}, username: {username}"
    )
    return token_data


@auth_router.get("/logout")
async def revoke_token(
    response: Response,
    refresh_token_details: dict = Depends(RefreshTokenFromCookie()),
    access_token_details: dict = Depends(AccessTokenFromCookie()),
    redis_client: RedisClient = Depends(get_redis_client),
    request: Request = None,
):
    user_id = refresh_token_details["user"]["id"]
    username = refresh_token_details["user"].get("username", "unknown")

    auth_logger.info(f"Logout attempt for user ID: {user_id}, username: {username}")

    try:
        # Add tokens to blocklist
        try:
            refresh_jti = refresh_token_details["jti"]
            access_jti = access_token_details["jti"]

            redis_client.add_jti_to_blocklist(refresh_jti)
            auth_logger.debug(f"Added refresh token to blocklist: JTI {refresh_jti}")

            redis_client.add_jti_to_blocklist(access_jti)
            auth_logger.debug(f"Added access token to blocklist: JTI {access_jti}")
        except Exception as redis_error:
            auth_logger.error(
                f"Redis error during token blocklisting: {str(redis_error)}"
            )
            # Continue even if blocklisting fails, as we still want to delete the cookies

        # Create a JSONResponse with the logout message
        response_content = {"message": "logged out successfully"}
        response = JSONResponse(content=response_content)

        # Delete cookies from the response
        response.delete_cookie(key="access_token")
        response.delete_cookie(key="refresh_token")

        auth_logger.info(
            f"User logged out successfully: ID {user_id}, username: {username}"
        )

        return response
    except Exception as e:
        auth_logger.error(f"Unexpected error during logout: {str(e)}")
        raise DatabaseException(detail="An unexpected error occurred during logout")


def generate_tokens_for_user(user) -> (str, str):
    access_token = create_access_token(
        {
            "id": str(user.id),
            "username": user.username,
            "role": user.role,
        }
    )

    refresh_token = create_refresh_token(
        {
            "id": str(user.id),
            "username": user.username,
        }
    )

    return access_token, refresh_token


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=Config.JWT_ACCESS_TOKEN_EXPIRY,
        httponly=True,
        secure=True,
        samesite="strict",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=Config.JWT_REFRESH_TOKEN_EXPIRY,
        httponly=True,
        secure=True,
        samesite="strict",
    )
