import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from src.judge.client import Judge0Client
from src.config import Config
from src.auth.dependency import get_current_user
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.main import get_session
from .model import UserSubmission
from sqlmodel import select

judge_router = APIRouter(tags=["Judge"])
judge_client = Judge0Client(Config.JUDGE0_URL, Config.JUDGE0_AUTH_TOKEN)


@judge_router.post("/submissions", status_code=201)
async def submit_code(
    source_code: str = Body(..., min_length=1),
    language_id: int = Body(71),
    problem_id: Optional[uuid.UUID] = Body(None),
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        print(f"[DEBUG] Створення submission для user_id: {user.uid}")
        token = await judge_client.submit_code(source_code, language_id)

        submission = UserSubmission(
            user_id=uuid.UUID(user.uid),
            submission_token=token,
            problem_id=problem_id,
        )
        session.add(submission)
        await session.commit()  # Обов'язковий коміт транзакції
        print(f"[DEBUG] Submission збережено: {submission.id}")
        await session.refresh(submission)  # Оновлення об'єкта

        print(f"[DEBUG] Збережено submission: {submission.id}")  # Логування
        return {"token": token}

    except Exception as e:
        await session.rollback()  # Відкат транзакції при помилці
        raise HTTPException(500, detail=str(e))


@judge_router.get("/submissions/{token}")
async def get_submission_details(
    token: str,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.run_sync(
        lambda sync_session: sync_session.execute(
            select(UserSubmission).where(
                (UserSubmission.submission_token == token)
                & (UserSubmission.user_id == user.uid)
            )
        )
    )
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(404, "Submission not found or access denied")

    try:
        judge_data = judge_client.get_result(token)
    except HTTPException as e:
        raise e

    return {
        "metadata": {
            "problem_id": submission.problem_id,
            "created_at": submission.created_at,
        },
        "result": judge_data,
    }


@judge_router.get("/my-submissions")
async def get_user_submissions(
    user=Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    print(f"Fetching submissions for user: {user.uid}")
    result = await session.run_sync(
        lambda sync_session: sync_session.execute(
            select(UserSubmission).where(UserSubmission.user_id == user.uid)
        )
    )
    submissions = result.scalars().all()
    print(f"Found submissions: {submissions}")
    detailed = []
    for sub in submissions:
        try:
            judge_data = judge_client.get_result(sub.submission_token)
            detailed.append(
                {
                    "id": sub.id,
                    "problem_id": sub.problem_id,
                    "created_at": sub.created_at,
                    "result": judge_data,
                }
            )
        except HTTPException:
            continue

    return detailed
