from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from src.judge.client import Judge0Client
from src.config import Config
from src.db.main import get_session
from src.judge.schema import (
    SubmissionRequest,
    SubmissionBrief,
    SubmissionDetail
)
from src.judge.service import (
    save_submission_to_db, fetch_submission_detail, fetch_user_submissions
)
from src.auth.dependency import get_current_user
from src.auth.schemas import UserModel, UserBaseResponse
import logging
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

judge_router = APIRouter()

judge_client = Judge0Client(Config.JUDGE0_URL, Config.JUDGE0_AUTH_TOKEN)


@judge_router.post("/submissions")
async def submit_code(
        submission_data: SubmissionRequest,
        session: AsyncSession = Depends(get_session),
        current_user: UserBaseResponse = Depends(get_current_user),
):
    try:
        submission_token = judge_client.submit_code(
            submission_data.source_code,
            submission_data.language_id,
            submission_data.stdin,
            submission_data.redirect_stderr_to_stdout,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting code: {str(e)}",
        )

    try:
        await save_submission_to_db(
            session=session,
            user_id=current_user.id,
            submission_token=submission_token,
            problem_id=None,
        )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )

    return {"submission_token": submission_token}


# src/judge/route.py
@judge_router.get("/submissions/{token}", response_model=SubmissionDetail)
async def get_submission_by_token(
        token: str,
        session: AsyncSession = Depends(get_session),
        current_user: UserModel = Depends(get_current_user),
):
    return await fetch_submission_detail(token, session, current_user, judge_client)


@judge_router.get("/submissions", response_model=List[SubmissionBrief])
async def get_user_submissions(
        session: AsyncSession = Depends(get_session),
        current_user: UserModel = Depends(get_current_user),
        limit: int = 100,
        offset: int = 0,
):
    return await fetch_user_submissions(session, current_user, judge_client, limit, offset)
