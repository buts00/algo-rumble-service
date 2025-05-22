import os
import time

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import UUID4
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


import uuid

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        origin = request.headers.get("origin")
        logger.info(
            f"Request started: {request.method} {request.url.path} - "
            f"ID: {request_id} - Client: {request.client.host} - Origin: {origin}"
        )
        start_time = time.time()
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path} - "
                f"ID: {request_id} - Status: {response.status_code} - "
                f"Time: {process_time:.4f}s - Response headers: {response.headers}"
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} - "
                f"ID: {request_id} - Error: {e} - "
                f"Time: {process_time:.4f}s"
            )
            raise


@asynccontextmanager
async def life_span(app: FastAPI):
    logger.info("Server is starting...")
    if os.environ.get("TESTING") != "True":
        try:
            await init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
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

# CORS: дозволити будь-який піддомен vercel.app та localhost:3000 для розробки
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://algo-rubmle.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Логування запитів
app.add_middleware(LoggingMiddleware)

# Rate limiting
redis_client = get_redis_client()
app.add_middleware(RateLimitMiddleware, redis_client=redis_client)
logger.info("Rate limiting middleware added")

# Обробники помилок
register_exception_handlers(app)

# Маршрути
app.include_router(auth_router,       prefix=f"/api/{version}", tags=["auth"])
app.include_router(match_router,      prefix=f"/api/{version}",      tags=["match"])
app.include_router(problem_router,    prefix=f"/api/{version}",      tags=["problem"])
app.include_router(testcase_router,   prefix=f"/api/{version}",      tags=["testcase"])
app.include_router(submission_router, prefix=f"/api/{version}",      tags=["submission"])

logger.info(f"Application startup complete - API version: {version}")