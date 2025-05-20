from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.business.services import get_current_user
from src.business.services.submission import SubmissionService
from src.config import logger
from src.data.repositories import get_session
from src.data.schemas import SubmissionCreate, UserBaseResponse
from src.errors import AuthorizationException

submission_logger = logger.getChild("submission")
submission_router = APIRouter(prefix="/submissions", tags=["submissions"])


@submission_router.post(
    "/match",
    summary="Submit a solution",
    description="Submits a solution for a match, runs it against test cases using OneCompiler API, and updates match status and ratings if correct."
)
async def submit_solution(
    submission_data: SubmissionCreate,
    db: AsyncSession = Depends(get_session),
    current_user: UserBaseResponse = Depends(get_current_user),
):
    if submission_data.user_id != current_user.id:
        submission_logger.warning(
            f"Unauthorized submission attempt: User ID {submission_data.user_id} != {current_user.id}"
        )
        raise AuthorizationException(detail="Not authorized to submit for another user")

    submission_logger.info(f"Processing submission for match ID: {submission_data.match_id}")
    return await SubmissionService.process_submission(
        str(submission_data.user_id),
        str(submission_data.match_id),
        submission_data.code,
        submission_data.language,
        db,
    )