import logging

import requests
from fastapi import HTTPException
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class Judge0Client:
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url
        self.headers = {"X-Auth-Token": auth_token}
        self._languages_cache = None

    def submit_code(
            self,
            source_code: str,
            language_id: int,
            stdin: Optional[str] = "",
            redirect_stderr_to_stdout: bool = True,
    ) -> Optional[str]:
        try:
            payload = {
                "source_code": source_code,
                "language_id": language_id,
                "stdin": stdin,
                "redirect_stderr_to_stdout": redirect_stderr_to_stdout,
            }

            response = requests.post(
                f"{self.base_url}/submissions",
                headers=self.headers,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("token")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Judge0 error: {str(e)}")

    def get_result(self, token: str) -> Dict[str, Any]:
        try:
            response = requests.get(
                f"{self.base_url}/submissions/{token}",
                headers=self.headers,
                timeout=10,
                params={
                    "fields": "stdout,stderr,source_code,status,language_id,time,memory,created_at,finished_at,exit_code,exit_signal,compile_output,stdin"
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Judge0 error: {str(e)}")

    def get_language_name(self, language_id: int) -> str:
        try:
            if self._languages_cache is None:
                response = requests.get(
                    f"{self.base_url}/languages",
                    headers=self.headers,
                    timeout=10
                )
                response.raise_for_status()
                self._languages_cache = {lang['id']: lang['name'] for lang in response.json()}

            return self._languages_cache.get(language_id, "Unknown")
        except Exception as e:
            logger.error(f"Error fetching languages: {str(e)}")
            return "Unknown"