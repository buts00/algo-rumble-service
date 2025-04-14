from fastapi import APIRouter, Depends, status, HTTPException, Response
from sqlalchemy.ext.asyncio.session import AsyncSession
from starlette.responses import JSONResponse

from .dependency import (
    get_user_service,
    RefreshTokenFromCookie,
    AccessTokenFromCookie,
)
from .schemas import UserCreateModel, UserLoginModel, UserResponseModel
from .service import UserService
from .util import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from src.db.main import get_session
from src.config import Config
from ..db.dependency import get_redis_client
from ..db.redis import RedisClient

auth_router = APIRouter()


@auth_router.post(
    "/register", response_model=UserResponseModel, status_code=status.HTTP_201_CREATED
)
async def create_user(
    response: Response,
    user_data: UserCreateModel,
    user_service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_session),
):
    user_exists = await user_service.get_user_by_username(user_data.username, session)

    if user_exists:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user with this username already exists",
        )

    new_user = await user_service.create_user(user_data, session)

    access_token, refresh_token = generate_tokens_for_user(new_user)

    await user_service.update_refresh_token(new_user.id, refresh_token, session)

    set_auth_cookies(response, access_token, refresh_token)

    return new_user


@auth_router.post("/login", response_model=UserResponseModel)
async def login(
    response: Response,
    login_data: UserLoginModel,
    user_service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_session),
):
    user = await user_service.get_user_by_username(login_data.username, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials"
        )

    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials"
        )

    access_token, refresh_token = generate_tokens_for_user(user)

    await user_service.update_refresh_token(user.id, refresh_token, session)

    set_auth_cookies(response, access_token, refresh_token)

    return user


@auth_router.get("/refresh-token")
async def update_tokens(
    response: Response,
    token_details: dict = Depends(RefreshTokenFromCookie()),
    user_service: UserService = Depends(get_user_service),
    redis_client: RedisClient = Depends(get_redis_client),
    session: AsyncSession = Depends(get_session),
):
    user_id = token_details["user"]["id"]

    user = await user_service.get_user_by_id(user_id, session)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials"
        )

    redis_client.add_jti_to_blocklist(token_details["jti"])

    access_token, refresh_token = generate_tokens_for_user(user)

    await user_service.update_refresh_token(user.id, refresh_token, session)

    set_auth_cookies(response, access_token, refresh_token)

    return {"Okay": "👍"}


@auth_router.get("/me")
async def get_current_user(token_data=Depends(AccessTokenFromCookie())):
    return token_data


@auth_router.get("/logout")
async def revoke_token(
    response: Response,
    refresh_token_details: dict = Depends(RefreshTokenFromCookie()),
    access_token_details: dict = Depends(AccessTokenFromCookie()),
    redis_client: RedisClient = Depends(get_redis_client),
):
    redis_client.add_jti_to_blocklist(refresh_token_details["jti"])
    redis_client.add_jti_to_blocklist(access_token_details["jti"])

    response = JSONResponse(
        content={"message": "logged out successfully"}, status_code=status.HTTP_200_OK
    )

    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")

    return response


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
