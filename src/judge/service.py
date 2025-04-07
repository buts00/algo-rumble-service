import uuid
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from src.judge.model import UserSubmission
from fastapi import HTTPException, status


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
