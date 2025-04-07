from abc import abstractmethod, ABC

from fastapi import Request, Depends, HTTPException, status
from .util import decode_token
from src.db.redis import RedisClient
from .service import UserService
from src.auth.schemas import UserBaseResponse
from ..db.dependency import get_redis_client


class TokenFromCookie(ABC):
    def __init__(self, cookie_name: str):
        self.cookie_name = cookie_name

    async def __call__(
        self, request: Request, redis_client: RedisClient = Depends(get_redis_client)
    ) -> dict:
        token = request.cookies.get(self.cookie_name)

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"{self.cookie_name} not found in cookies",
            )

        token_data = decode_token(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired token",
            )

        if redis_client.token_in_blocklist(token_data["jti"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token is blacklisted",
            )

        self.verify_token_data(token_data)
        return token_data

    @abstractmethod
    def verify_token_data(self, token_data: dict): ...


class AccessTokenFromCookie(TokenFromCookie):
    def __init__(self):
        super().__init__("access_token")

    def verify_token_data(self, token_data: dict):
        if token_data.get("is_refresh"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access token required",
            )


class RefreshTokenFromCookie(TokenFromCookie):
    def __init__(self):
        super().__init__("refresh_token")

    def verify_token_data(self, token_data: dict):
        if not token_data.get("is_refresh"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Refresh token required",
            )


def get_current_user(
    token_data: dict = Depends(AccessTokenFromCookie()),
) -> UserBaseResponse:
    try:
        user = UserBaseResponse(**token_data["user"])
        return user
    except Exception as _:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate user",
        )


def get_user_service() -> UserService:
    return UserService()
