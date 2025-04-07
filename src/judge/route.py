from fastapi import APIRouter, HTTPException, Depends, status, Cookie, Response
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from src.judge.client import Judge0Client
from src.config import Config
from src.db.main import get_session
from src.judge.schema import SubmissionRequest
from src.judge.service import save_submission_to_db
from src.auth.dependency import get_current_user
from src.auth.schemas import UserModel, TokenUser
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
judge_router = APIRouter()

judge_client = Judge0Client(Config.JUDGE0_URL, Config.JUDGE0_AUTH_TOKEN)


@judge_router.post("/submissions")
async def submit_code(
    response: Response,
    submission_data: SubmissionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: TokenUser = Depends(get_current_user),
):
    try:
        token = judge_client.submit_code(
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
            submission_token=token,
            problem_id=None,
        )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )

    return token


@judge_router.get("/submissions/{token}")
async def get_result(
    response: Response,
    token: str,
    current_user: UserModel = Depends(get_current_user),
):
    logger.info(f"GET /submissions/{token} called")
    logger.info(f"Current user: {current_user}")
    try:
        result = judge_client.get_result(token)
        logger.info(f"Judge result: {result}")
    except Exception as e:
        logger.error(f"Exception while getting result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving result: {str(e)}",
        )

    return result
