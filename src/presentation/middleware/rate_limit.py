from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from src.config import logger
from src.data.repositories import RedisClient


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting requests based on client IP address.
    Uses Redis to track request counts per client IP.
    """

    def __init__(self, app, redis_client: RedisClient):
        super().__init__(app)
        self.redis_client = redis_client
        self.rate_limit_logger = logger.getChild("rate_limit")

        # Default rate limits (requests per minute)
        self.default_rate_limit = 100

        # Endpoint-specific rate limits
        self.endpoint_rate_limits = {
            # Auth endpoints - higher limits for registration and login
            "/api/v1/auth/register": 20,
            "/api/v1/auth/login": 30,
            # Match endpoints - lower limits for match finding to prevent abuse
            "/api/v1/match/find": 10,
            # WebSocket endpoints - higher limits
            "/api/v1/match/ws": 200,
        }

        # Window size in seconds (1 minute)
        self.window = 60

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for certain paths
        if (
            request.url.path.startswith("/docs")
            or request.url.path.startswith("/redoc")
            or request.url.path.startswith("/openapi")
        ):
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host

        # Get the rate limit for this endpoint
        path = request.url.path
        rate_limit = self.endpoint_rate_limits.get(path, self.default_rate_limit)

        # Create a key for Redis
        key = f"rate_limit:{client_ip}:{path}"

        # Check if rate limit is exceeded
        current_count = self.redis_client.get(key) or 0
        current_count = int(current_count)

        if current_count >= rate_limit:
            self.rate_limit_logger.warning(
                f"Rate limit exceeded: IP {client_ip}, Path {path}, "
                f"Count {current_count}, Limit {rate_limit}"
            )
            return JSONResponse(
                content={"detail": "Rate limit exceeded. Please try again later."},
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
            )

        # Increment counter and set expiry if not exists
        if not self.redis_client.exists(key):
            self.redis_client.set(key, 1, ex=self.window)
        else:
            self.redis_client.incr(key)

        # Log the request (only if approaching limit to avoid excessive logging)
        if current_count > rate_limit * 0.8:
            self.rate_limit_logger.info(
                f"Request approaching rate limit: IP {client_ip}, Path {path}, "
                f"Count {current_count + 1}, Limit {rate_limit}"
            )

        # Process the request
        return await call_next(request)
