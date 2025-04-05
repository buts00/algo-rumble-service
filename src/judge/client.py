import requests
from fastapi import HTTPException
from typing import Optional
from aiohttp import ClientError

logger = logging.getLogger(__name__)


class Judge0Client:
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url
        self.headers = {"X-Auth-Token": auth_token}

    def submit_code(self, source_code: str, language_id: int = 71) -> Optional[str]:
        try:
            response = requests.post(
                f"{self.base_url}/submissions",
                headers=self.headers,
                json={"source_code": source_code, "language_id": language_id},
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("token")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Judge0 error: {str(e)}")

    def get_result(self, token: str) -> dict:
        try:
            response = requests.get(
                f"{self.base_url}/submissions/{token}", headers=self.headers, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Judge0 error: {str(e)}")
