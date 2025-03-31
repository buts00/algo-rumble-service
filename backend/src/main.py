from fastapi import FastAPI
from backend.src.auth.routes import auth_router
from backend.src.judge.routes import judge_router
from contextlib import asynccontextmanager
from backend.src.db.main import init_db


@asynccontextmanager
async def life_span(app: FastAPI):
    print("Server is starting...")
    await init_db()
    yield
    print("Server has been stopped")


version = "v1"
app = FastAPI(
    title="Algo Rumble API",
    description="A platform for 1-on-1 algorithmic competitions with a rating system and task topic management",
    version=version,
    lifespan=life_span,
)

app.include_router(auth_router, prefix=f"/api/{version}/auth", tags=["auth"])
app.include_router(judge_router, prefix=f"/api/{version}/judge", tags=["judge"])
