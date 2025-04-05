from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.judge.client import Judge0Client
from src.config import Config
from src.db.main import get_session
from src.judge.schema import SubmissionRequest
from src.judge.service import save_submission_to_db
from src.auth.dependency import get_current_user
from src.auth.schemas import UserModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
judge_router = APIRouter()

judge_client = Judge0Client(Config.JUDGE0_URL, Config.JUDGE0_AUTH_TOKEN)


@judge_router.post("/submissions")
async def submit_code(
    submission_data: SubmissionRequest,
    db: Session = Depends(get_session),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        token = judge_client.submit_code(
            submission_data.source_code, submission_data.language_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting code: {str(e)}",
        )

    try:
        logger.info(current_user.uid)
        logger.info(token)
        await save_submission_to_db(
            session=db,
            user_id=current_user.uid,
            submission_token=token,
            problem_id=submission_data.problem_id,
        )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )

    return {"token": token}


@judge_router.get("/submissions/{token}")
async def get_result(token: str, current_user: UserModel = Depends(get_current_user)):
    try:
        result = judge_client.get_result(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving result: {str(e)}",
        )

    return result
