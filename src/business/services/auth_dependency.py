from fastapi import Depends, HTTPException, Request, status
from starlette.websockets import WebSocket, WebSocketDisconnect
from src.data.schemas import UserBaseResponse

class TokenFromCookie:
    def __init__(self, cookie_name: str = "access_token"):
        self.cookie_name = cookie_name

    async def __call__(self, request: Request) -> dict:
        token = request.cookies.get(self.cookie_name)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"{self.cookie_name} not found in cookies"
            )

        from src.business.services.auth_util import decode_token
        token_data = decode_token(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired token"
            )

        return token_data

AccessTokenFromCookie = TokenFromCookie

class RefreshTokenFromCookie(TokenFromCookie):
    def __init__(self):
        super().__init__(cookie_name="refresh_token")

def get_current_user(token_data: dict = Depends(AccessTokenFromCookie())) -> UserBaseResponse:
    try:
        user = UserBaseResponse(**token_data["user"])
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate user"
        )