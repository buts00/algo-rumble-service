import json
import uuid
from typing import List, Dict, Any

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.data.repositories.s3 import upload_problem_to_s3, upload_testcase_to_s3
from src.data.schemas import Problem
from src.data.schemas.problem import (
    ProblemCreate,
    ProblemResponse,

)
from src.data.schemas.testcase import TestCaseResponse
from src.errors import DatabaseException, ResourceNotFoundException

problem_logger = logger.getChild("problem_repository")


async def create_problem_in_db(
    db: AsyncSession, problem_data: ProblemCreate
) -> ProblemResponse:
    try:
        problem_id = uuid.uuid4()
        problem_logger.info(f"Створюємо проблему з ID: {problem_id}, дані: {problem_data.dict()}")

        # Створюємо проблему в базі даних
        db_problem = Problem(
            id=problem_id,
            rating=problem_data.rating,
            topics=problem_data.topics,
            title=problem_data.problem.title,
            description=problem_data.problem.description,
            time_limit=problem_data.problem.time_limit,
            memory_limit=problem_data.problem.memory_limit,
            input_description=problem_data.problem.input_description,
            output_description=problem_data.problem.output_description,
            examples=problem_data.problem.examples,
            constraints=problem_data.problem.constraints,
        )
        db.add(db_problem)
        await db.commit()
        await db.refresh(db_problem)

        # Завантажуємо дані проблеми в DigitalOcean Spaces
        problem_data_json = json.dumps(
            {
                "title": db_problem.title,
                "description": db_problem.description,
                "time_limit": db_problem.time_limit,
                "memory_limit": db_problem.memory_limit,
                "input_description": db_problem.input_description,
                "output_description": db_problem.output_description,
                "examples": db_problem.examples,
                "constraints": db_problem.constraints,
            }
        )
        s3_key = f"problems/{db_problem.id}/problem.json"
        await upload_problem_to_s3(s3_key, problem_data_json)

        problem_logger.info(f"Створено проблему з ID: {db_problem.id}")
        return ProblemResponse.from_orm(db_problem)
    except Exception as e:
        problem_logger.error(f"Не вдалося створити проблему: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail=f"Не вдалося створити проблему: {str(e)}")


async def create_testcases_in_db(
    db: AsyncSession, problem_id: uuid.UUID, testcases: List[Dict[str, str]]
) -> TestCaseResponse:
    """Створює тестові випадки для проблеми і завантажує їх у DigitalOcean Spaces."""
    try:
        # Перевіряємо, чи існує проблема
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise ResourceNotFoundException(detail=f"Проблему {problem_id} не знайдено")

        # Створюємо тестові випадки в DigitalOcean Spaces
        testcase_ids = []
        for idx, tc in enumerate(testcases, 1):
            testcase_id = uuid.uuid4()
            testcase_data_json = json.dumps(
                {"input": tc["input"], "output": tc["output"]}
            )
            s3_key = f"problems/{problem_id}/testcases/{testcase_id}.json"
            await upload_testcase_to_s3(s3_key, testcase_data_json)
            testcase_ids.append(testcase_id)

        problem_logger.info(
            f"Створено {len(testcases)} тестових випадків для проблеми з ID: {problem_id}"
        )
        return TestCaseResponse(problem_id=problem_id, testcase_ids=testcase_ids)
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

        # Оновлюємо дані проблеми в DigitalOcean Spaces
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