import json
from typing import Any, Dict, List

from pydantic.v1 import UUID4
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.data.repositories.s3 import upload_problem_to_s3, upload_testcase_to_s3
from src.data.schemas import Problem, ProblemCreate, ProblemResponse, TestCaseResponse
from src.errors import DatabaseException, ResourceNotFoundException

problem_logger = logger.getChild("problem_repository")


async def create_problem_in_db(
    db: AsyncSession, problem_data: ProblemCreate
) -> ProblemResponse:
    """Create a new problem in the database and upload to DigitalOcean Spaces."""
    try:
        # Create problem in database
        db_problem = Problem(
            id=UUID4(),
            rating=problem_data.rating,
            topics=problem_data.topics,
            name=problem_data.problem.name,
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

        # Upload problem data to DigitalOcean Spaces
        problem_data_json = json.dumps(
            {
                "name": db_problem.name,
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

        problem_logger.info(f"Created problem ID: {db_problem.id}")
        return ProblemResponse.from_orm(db_problem)
    except Exception as e:
        problem_logger.error(f"Failed to create problem: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail="Failed to create problem")


async def create_testcases_in_db(
    db: AsyncSession, problem_id: UUID4, testcases: List[Dict[str, str]]
) -> TestCaseResponse:
    """Create test cases for a problem and upload them to DigitalOcean Spaces."""
    try:
        # Verify problem exists
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise ResourceNotFoundException(detail=f"Problem {problem_id} not found")

        # Create test cases in DigitalOcean Spaces
        testcase_ids = []
        for idx, tc in enumerate(testcases, 1):
            testcase_id = UUID4()
            testcase_data_json = json.dumps(
                {"input": tc["input"], "output": tc["output"]}
            )
            s3_key = f"problems/{problem_id}/testcases/{testcase_id}.json"
            await upload_testcase_to_s3(s3_key, testcase_data_json)
            testcase_ids.append(testcase_id)

        problem_logger.info(
            f"Created {len(testcases)} testcases for problem ID: {problem_id}"
        )
        return TestCaseResponse(problem_id=problem_id, testcase_ids=testcase_ids)
    except ResourceNotFoundException:
        raise
    except Exception as e:
        problem_logger.error(
            f"Failed to create testcases for problem {problem_id}: {str(e)}"
        )
        raise DatabaseException(detail="Failed to create testcases")


async def get_problem_by_id(db: AsyncSession, problem_id: UUID4) -> ProblemResponse:
    """Retrieve a problem by its ID."""
    try:
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise ResourceNotFoundException(detail=f"Problem {problem_id} not found")
        problem_logger.info(f"Retrieved problem ID: {problem_id}")
        return ProblemResponse.from_orm(problem)
    except ResourceNotFoundException:
        raise
    except Exception as e:
        problem_logger.error(f"Failed to retrieve problem {problem_id}: {str(e)}")
        raise DatabaseException(detail="Failed to retrieve problem")


async def update_problem_in_db(
    db: AsyncSession, problem_id: UUID4, update_data: Dict[str, Any]
) -> ProblemResponse:
    """Update a problem in the database and DigitalOcean Spaces."""
    try:
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise ResourceNotFoundException(detail=f"Problem {problem_id} not found")

        # Update problem in database
        await db.execute(
            update(Problem).where(Problem.id == problem_id).values(**update_data)
        )
        await db.commit()
        await db.refresh(problem)

        # Update problem data in DigitalOcean Spaces
        problem_data_json = json.dumps(
            {
                "name": problem.name,
                "description": problem.description,
                "time_limit": problem.time_limit,
                "memory_limit": problem.time_limit,
                "input_description": problem.input_description,
                "output_description": problem.output_description,
                "examples": problem.examples,
                "constraints": problem.constraints,
            }
        )
        s3_key = f"problems/{problem_id}/problem.json"
        await upload_problem_to_s3(s3_key, problem_data_json)

        problem_logger.info(f"Updated problem ID: {problem_id}")
        return ProblemResponse.from_orm(problem)
    except ResourceNotFoundException:
        raise
    except Exception as e:
        problem_logger.error(f"Failed to update problem {problem_id}: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail="Failed to update problem")


async def delete_problem_from_db(db: AsyncSession, problem_id: UUID4) -> dict:
    """Delete a problem from the database and note that DigitalOcean Spaces cleanup is needed."""
    try:
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise ResourceNotFoundException(detail=f"Problem {problem_id} not found")

        # Delete problem from database
        await db.execute(delete(Problem).where(Problem.id == problem_id))
        await db.commit()

        # Note: DigitalOcean Spaces testcases cleanup should be handled separately (e.g., via S3 lifecycle rules)
        problem_logger.info(f"Deleted problem ID: {problem_id}")
        return {"message": f"Problem {problem_id} deleted successfully"}
    except ResourceNotFoundException:
        raise
    except Exception as e:
        problem_logger.error(f"Failed to delete problem {problem_id}: {str(e)}")
        await db.rollback()
        raise DatabaseException(detail="Failed to delete problem")


async def list_problems_from_db(
    db: AsyncSession, skip: int, limit: int
) -> List[ProblemResponse]:
    """List problems with pagination."""
    try:
        result = await db.execute(
            select(Problem)
            .offset(skip)
            .limit(limit)
            .order_by(Problem.created_at.desc())
        )
        problems = result.scalars().all()
        problem_logger.info(
            f"Listed {len(problems)} problems with skip: {skip}, limit: {limit}"
        )
        return [ProblemResponse.from_orm(problem) for problem in problems]
    except Exception as e:
        problem_logger.error(f"Failed to list problems: {str(e)}")
        raise DatabaseException(detail="Failed to list problems")