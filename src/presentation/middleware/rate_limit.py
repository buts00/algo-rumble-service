from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from src.data.repositories.redis import RedisClient

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client: RedisClient):
        super().__init__(app)
        self.redis_client = redis_client
        self.rate_limit = 100  # Example: 100 requests per minute
        self.rate_limit_window = 60  # Time window in seconds

    async def dispatch(self, request: Request, call_next):
        # Get client IP or user identifier
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"

        # Increment request count in Redis
        try:
            request_count = await self.redis_client.incr(key)
            if request_count == 1:
                # Set expiry for the key if it's the first request
                await self.redis_client.set(key, request_count, ex=self.rate_limit_window)

            # Check if rate limit is exceeded
            if request_count > self.rate_limit:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later."
                )
        except Exception as e:
            # Log error but don't block the request if Redis fails
            print(f"Rate limit error: {str(e)}")

        # Proceed with the request
        response = await call_next(request)
        return response