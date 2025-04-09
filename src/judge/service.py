import uuid
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from src.judge.model import UserSubmission
from fastapi import HTTPException, status
from typing import List, Optional
from src.judge.client import Judge0Client
from src.judge.schema import SubmissionDetail, SubmissionBrief
from src.auth.schemas import UserModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def save_submission_to_db(
        session: AsyncSession,
        user_id: uuid.UUID,
        submission_token: str,
        problem_id: uuid.UUID | None = None,
) -> UserSubmission:
    try:
        submission = UserSubmission(
            user_id=user_id, submission_token=submission_token, problem_id=problem_id
        )

        session.add(submission)
        await session.commit()
        await session.refresh(submission)

        return submission
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving submission to the database",
        ) from e


async def get_user_submission_by_token(
        session: AsyncSession,
        user_id: uuid.UUID,
        submission_token: str,
) -> Optional[UserSubmission]:
    try:
        result = await session.execute(
            select(UserSubmission)
            .where(UserSubmission.user_id == user_id)
            .where(UserSubmission.submission_token == submission_token)
        )
        return result.scalars().first()
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching submission from database",
        ) from e


async def get_all_user_submissions(
        session: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
) -> List[UserSubmission]:
    try:
        result = await session.execute(
            select(UserSubmission)
            .where(UserSubmission.user_id == user_id)
            .order_by(UserSubmission.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching user submissions from database",
        ) from e


async def fetch_submission_detail(
        token: str, session: AsyncSession, current_user: UserModel, judge_client: Judge0Client
) -> SubmissionDetail:
    db_submission = await get_user_submission_by_token(
        session=session,
        user_id=current_user.id,
        submission_token=token
    )

    if not db_submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found or not owned by user",
        )

    submission_result = judge_client.get_result(token)
    language_id = submission_result.get("language_id")
    language_name = judge_client.get_language_name(language_id)

    return SubmissionDetail(
        source_code=submission_result.get("source_code", ""),
        language_id=language_id,
        language_name=language_name,
        status=submission_result.get("status", {}),
        stdin=submission_result.get("stdin", ""),
        stdout=submission_result.get("stdout", ""),
        stderr=submission_result.get("stderr", ""),
        compile_output=submission_result.get("compile_output", ""),
        time=submission_result.get("time"),
        memory=submission_result.get("memory"),
        created_at=db_submission.created_at,
        problem_id=db_submission.problem_id,
        exit_code=submission_result.get("exit_code"),
        exit_signal=submission_result.get("exit_signal"),
    )


async def fetch_user_submissions(
        session: AsyncSession, current_user: UserModel, judge_client: Judge0Client, limit: int, offset: int
) -> List[SubmissionBrief]:
    db_submissions = await get_all_user_submissions(
        session=session,
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )

    if not db_submissions:
        return []

    result = []
    for submission in db_submissions:
        try:
            submission_result = judge_client.get_result(submission.submission_token)
            language_id = submission_result.get("language_id")
            language_name = judge_client.get_language_name(language_id)

            result.append(SubmissionBrief(
                submission_token=submission.submission_token,
                status=submission_result.get("status", {}),
                time=submission_result.get("time"),
                memory=submission_result.get("memory"),
                created_at=submission.created_at,
                problem_id=submission.problem_id,
                language_id=language_id,
                language_name=language_name
            ))
        except Exception as e:
            logger.error(f"Error fetching submission {submission.submission_token}: {str(e)}")
            result.append(SubmissionBrief(
                submission_token=submission.submission_token,
                status={"id": -1, "description": "Error fetching result"},
                time=None,
                memory=None,
                created_at=submission.created_at,
                problem_id=submission.problem_id,
                language_id=-1,
                language_name="Unknown"
            ))

    return result
