import aiohttp
import logging
from fastapi import HTTPException
from typing import Optional
from aiohttp import ClientError

logger = logging.getLogger(__name__)


class Judge0Client:
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url
        self.headers = {"X-Auth-Token": auth_token}

    async def submit_code(self, source_code: str, language_id: int) -> Optional[str]:
        if not source_code.strip():
            raise HTTPException(status_code=400, detail="Source code cannot be empty")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/submissions",
                    headers=self.headers,
                    json={"source_code": source_code, "language_id": language_id},
                    timeout=10,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("token")
        except ClientError as e:
            logger.error(f"Judge0 submit_code error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Judge0 error: {str(e)}")

    async def get_result(self, token: str) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/submissions/{token}",
                    headers=self.headers,
                    timeout=10,
                ) as response:
                    response.raise_for_status()
                    return await response.json()
        except ClientError as e:
            logger.error(f"Judge0 get_result error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Judge0 error: {str(e)}")
