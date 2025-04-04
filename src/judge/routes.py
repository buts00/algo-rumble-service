from fastapi import APIRouter
from src.judge.client import Judge0Client
from src.config import Config

judge_router = APIRouter()


judge_client = Judge0Client(Config.JUDGE0_URL, Config.JUDGE0_AUTH_TOKEN)


@judge_router.post("/submissions")
async def submit_code(source_code: str, language_id: int = 71):
    token = judge_client.submit_code(source_code, language_id)
    return {"token": token}


@judge_router.get("/submissions/{token}")
async def get_result(token: str):
    result = judge_client.get_result(token)
    return result
