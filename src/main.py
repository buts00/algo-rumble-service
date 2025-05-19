import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.presentation.routes import (
    auth_router,
    match_router,
    problem_router,
    testcase_router,
    submission_router,
)
from src.config import logger
from src.data.repositories import get_redis_client, init_db
from src.errors import register_exception_handlers
from src.presentation.middleware.rate_limit import RateLimitMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Log request details
        logger.info(
            f"Request started: {request.method} {request.url.path} - ID: {request_id} - "
            f"Client: {request.client.host}"
        )

        # Measure request processing time
        start_time = time.time()

        try:
            response = await call_next(request)

            # Log response details
            process_time = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path} - ID: {request_id} - "
                f"Status: {response.status_code} - Time: {process_time:.4f}s"
            )

            return response
        except Exception as e:
            # Log exceptions
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} - ID: {request_id} - "
                f"Error: {str(e)} - Time: {process_time:.4f}s"
            )
            raise


@asynccontextmanager
async def life_span(_app: FastAPI):
    logger.info("Server is starting...")
    # Skip database initialization when running tests
    if os.environ.get("TESTING") != "True":
        try:
            await init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
    else:
        logger.info("Skipping database initialization for tests")
    yield
    logger.info("Server has been stopped")


version = "v1"
app = FastAPI(
    title="Algo Rumble API",
    description="A platform for 1-on-1 algorithmic competitions with a rating system and task topic management",
    version=version,
    lifespan=life_span,
)

# Add CORS middleware
origins = [
    "http://localhost:3000",
    "https://algo-rubmle.vercel.app",
]

def is_allowed_origin(origin: str) -> bool:
    return origin.endswith(".vercel.app") or origin in origins

class CustomCORSMiddleware(CORSMiddleware):
    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin")
        if origin and not is_allowed_origin(origin):
            return Response("CORS origin not allowed", status_code=403)
        return await super().dispatch(request, call_next)

app.add_middleware(
    CustomCORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Add rate limiting middleware
redis_client = get_redis_client()
app.add_middleware(RateLimitMiddleware, redis_client=redis_client)
logger.info("Rate limiting middleware added")

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(auth_router, prefix=f"/api/{version}/auth", tags=["auth"])
app.include_router(match_router, prefix=f"/api/{version}", tags=["match"])
app.include_router(problem_router, prefix=f"/api/{version}", tags=["problem"])
app.include_router(testcase_router, prefix=f"/api/{version}", tags=["testcase"])
app.include_router(submission_router, prefix=f"/api/{version}", tags=["submission"])
# Log application startup
logger.info(f"Application startup complete - API version: {version}")
