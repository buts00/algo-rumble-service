from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from src.data.repositories.redis_dependency import get_redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware to restrict requests per client."""

    def __init__(self, app, limit: int = 100, window: int = 60):
        super().__init__(app)
        self.limit = limit  # Max requests per window
        self.window = window  # Window in seconds

    async def dispatch(self, request: Request, call_next):
        redis = await get_redis_client()
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"

        # Get current request count
        current_count = await redis.get(key)  # Await the coroutine
        current_count = int(current_count or 0)  # Handle None, decode bytes if needed

        if current_count >= self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"}
            )

        # Increment count and set expiry
        await redis.incr(key)
        await redis.expire(key, self.window)

        response = await call_next(request)
        return response