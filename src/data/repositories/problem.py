import json
import uuid
from typing import List, Dict, Any

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.data.repositories.s3 import upload_testcase_to_s3

from src.data.schemas.testcase import TestCaseResponse
from src.errors import DatabaseException, ResourceNotFoundException

problem_logger = logger.getChild("problem_repository")

from src.data.schemas import Problem, ProblemCreate, ProblemResponse, ProblemDetail
from sqlalchemy.orm import Session
import uuid
from datetime import datetime
from src.data.repositories.s3 import upload_problem_to_s3
from fastapi import HTTPException


from sqlalchemy.ext.asyncio import AsyncSession

import uuid
from datetime import datetime

async def create_problem_in_db(db: AsyncSession, problem: ProblemCreate):
    try:
        new_problem = Problem(
            id=uuid.uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            rating=problem.rating,
            topics=problem.topics,
        )
        db.add(new_problem)
        await db.commit()
        await db.refresh(new_problem)
        # Явно серіалізуємо ProblemDetail
        problem_data = problem.problem.dict()
        # Перетворюємо datetime і UUID у рядки
        def convert_to_json_serializable(data):
            if isinstance(data, dict):
                return {k: convert_to_json_serializable(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [convert_to_json_serializable(item) for item in data]
            elif isinstance(data, uuid.UUID):
                return str(data)
            elif isinstance(data, datetime):
                return data.isoformat()  # Перетворюємо datetime у ISO формат
            return data
        problem_data = convert_to_json_serializable(problem_data)
        await upload_problem_to_s3(str(new_problem.id), problem_data)
        return new_problem
    except Exception as e:
        problem_logger.error(f"Error in create_problem_in_db: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "type": "error",
                "title": "Failed to create problem",
                "status": 500,
                "detail": str(e)
            }
        )

async def create_testcases_in_db(
    db: AsyncSession, problem_id: uuid.UUID, testcases: List[Dict[str, str]]
) -> TestCaseResponse:
    try:
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise ResourceNotFoundException(detail=f"Проблему {problem_id} не знайдено")

        testcase_ids = []
        for idx, tc in enumerate(testcases, 1):
            testcase_id = uuid.uuid4()
            input_data = tc["input"]
            output_data = tc["output"]
            await upload_testcase_to_s3(str(problem_id), idx, input_data, output_data)
            testcase_ids.append(testcase_id)

        problem_logger.info(
            f"Створено {len(testcases)} тестових випадків для проблеми з ID: {problem_id}"
        )
        return TestCaseResponse(
            problem_id=problem_id,
            testcase_count=len(testcases),
            success=True,
            message="Test cases created successfully"
        )
    except ResourceNotFoundException:
        raise
    except Exception as e:
        problem_logger.error(
            f"Не вдалося створити тестові випадки для проблеми {problem_id}: {str(e)}"
        )
        raise DatabaseException(detail=f"Не вдалося створити тестові випадки: {str(e)}")


async def get_problem_by_id(db: AsyncSession, problem_id: uuid.UUID) -> ProblemResponse:
    """Отримує проблему за її ID."""
    try:
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise ResourceNotFoundException(detail=f"Проблему {problem_id} не знайдено")
        problem_logger.info(f"Отримано проблему з ID: {problem_id}")
        return ProblemResponse.from_orm(problem)
    except ResourceNotFoundException:
        raise
    except Exception as e:
        problem_logger.error(f"Не вдалося отримати проблему {problem_id}: {str(e)}")
        raise DatabaseException(detail=f"Не вдалося отримати проблему: {str(e)}")


async def update_problem_in_db(
    db: AsyncSession, problem_id: uuid.UUID, update_data: Dict[str, Any]
) -> ProblemResponse:
    """Оновлює проблему в базі даних і DigitalOcean Spaces."""
    try:
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise ResourceNotFoundException(detail=f"Проблему {problem_id} не знайдено")

        # Оновлюємо проблему в базі даних
        await db.execute(
            update(Problem).where(Problem.id == problem_id).values(**update_data)
        )
        await db.commit()
        await db.refresh(problem)

        problem_data_json = json.dumps(
            {
                "title": problem.title,
                "description": problem.description,
                "time_limit": problem.time_limit,
                "memory_limit": problem.memory_limit,
                "input_description": problem.input_description,
                "output_description": problem.output_description,
                "examples": problem.examples,
                "constraints": problem.constraints,
            }
        )
        s3_key = f"problems/{problem_id}/problem.json"
        await upload_problem_to_s3(s3_key, problem_data_json)

        problem_logger.info(f"Оновлено проблему з ID: {problem_id}")
        return ProblemResponse.from_orm(problem)
    except ResourceNotFoundException:
        raise
    except Exception as e:
        problem_logger.error(f"Не вдалося оновити проблему {problem_id}: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail=f"Не вдалося оновити проблему: {str(e)}")


async def delete_problem_from_db(db: AsyncSession, problem_id: uuid.UUID) -> dict:
    """Видаляє проблему з бази даних, зауважуючи, що очищення DigitalOcean Spaces потрібне окремо."""
    try:
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise ResourceNotFoundException(detail=f"Проблему {problem_id} не знайдено")

        # Видаляємо проблему з бази даних
        await db.execute(delete(Problem).where(Problem.id == problem_id))
        await db.commit()

        # Примітка: очищення тестових випадків у DigitalOcean Spaces потрібно обробляти окремо
        problem_logger.info(f"Видалено проблему з ID: {problem_id}")
        return {"message": f"Проблему {problem_id} успішно видалено"}
    except ResourceNotFoundException:
        raise
    except Exception as e:
        problem_logger.error(f"Не вдалося видалити проблему {problem_id}: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail=f"Не вдалося видалити проблему: {str(e)}")


async def list_problems_from_db(
    db: AsyncSession, skip: int, limit: int
) -> List[ProblemResponse]:
    """Повертає список проблем з пагінацією."""
    try:
        result = await db.execute(
            select(Problem)
            .offset(skip)
            .limit(limit)
            .order_by(Problem.created_at.desc())
        )
        problems = result.scalars().all()
        problem_logger.info(
            f"Отримано список з {len(problems)} проблем, skip: {skip}, limit: {limit}"
        )
        return [ProblemResponse.from_orm(problem) for problem in problems]
    except Exception as e:
        problem_logger.error(f"Не вдалося отримати список проблем: {str(e)}")
        raise DatabaseException(detail=f"Не вдалося отримати список проблем: {str(e)}")