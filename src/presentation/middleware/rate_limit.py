from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from src.data.repositories.redis_dependency import get_redis_client

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 100, window: int = 60):
        super().__init__(app)
        self.limit = limit  # Max requests allowed in the window
        self.window = window  # Time window in seconds

    async def dispatch(self, request: Request, call_next):
        redis = get_redis_client()  # Synchronous call, no 'await'
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"

        # Get current request count
        count = await redis.get(key)
        if count is None:
            # First request, set initial count
            await redis.set(key, 1, ex=self.window)
        elif int(count) >= self.limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        else:
            # Increment count
            await redis.incr(key)

        # Proceed with the request
        response = await call_next(request)
        return response