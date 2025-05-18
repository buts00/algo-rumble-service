import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import logger
from src.data.repositories import get_session
from src.errors import DatabaseException, ResourceNotFoundException
from src.data.schemas import Problem
from src.data.schemas.problem_schemas import (
    ProblemCreate,
    ProblemResponse,
    ProblemUpdate,
)
from src.data.schemas.problem_schemas import TestCaseCreate, TestCaseResponse
from src.data.repositories import upload_problem_to_s3, upload_testcase_to_s3

# Create a module-specific logger
problem_logger = logger.getChild("problem")

problem_router = APIRouter(prefix="/problems", tags=["problems"])
testcase_router = APIRouter(prefix="/testcases", tags=["testcases"])


@testcase_router.post("/", response_model=TestCaseResponse)
async def create_testcases(
    testcase_data: TestCaseCreate,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Create test cases for a problem and upload them to DigitalOcean Spaces.
    """
    problem_id = testcase_data.problem_id
    problem_logger.info(f"Creating test cases for problem: ID {problem_id}")

    try:
        # Convert string problem_id to UUID for database query
        try:
            uuid_problem_id = uuid.UUID(problem_id)
        except ValueError:
            problem_logger.warning(f"Invalid problem ID format: {problem_id}")
            raise ResourceNotFoundException(detail="Invalid problem ID format")

        # Check if the problem exists
        result = await db.execute(select(Problem).where(Problem.id == uuid_problem_id))
        problem = result.scalars().first()

        if not problem:
            problem_logger.warning(f"Problem not found: ID {problem_id}")
            raise ResourceNotFoundException(detail="Problem not found")

        # Upload each test case to DigitalOcean Spaces
        testcase_count = 0
        for i, testcase in enumerate(testcase_data.testcases, start=1):
            try:
                # Upload the test case to S3
                upload_testcase_to_s3(problem_id, i, testcase.input, testcase.output)
                testcase_count += 1
                problem_logger.info(
                    f"Test case {i} uploaded for problem: ID {problem_id}"
                )
            except Exception as s3_error:
                problem_logger.error(
                    f"Error uploading test case {i} to S3: {str(s3_error)}"
                )
                # Continue with the next test case even if this one fails

        problem_logger.info(
            f"Created {testcase_count} test cases for problem: ID {problem_id}"
        )
        return TestCaseResponse(
            problem_id=uuid_problem_id,
            testcase_count=testcase_count,
            success=True,
            message=f"Successfully created {testcase_count} test cases",
        )
    except ResourceNotFoundException:
        raise
    except Exception as e:
        problem_logger.error(f"Unexpected error creating test cases: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while creating test cases"
        )


@problem_router.post("/", response_model=ProblemResponse)
async def create_problem(
    problem: ProblemCreate,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Create a new problem.
    """
    problem_logger.info(f"Creating new problem with rating: {problem.rating}")

    try:
        # Create a new problem instance
        new_problem = Problem(
            rating=problem.rating,
            topics=problem.topics,
            problem_data=problem.problem.model_dump(),
        )

        # Add to database to get an ID
        db.add(new_problem)
        await db.commit()
        await db.refresh(new_problem)

        # Upload problem to DigitalOcean Spaces
        problem_id = str(new_problem.id)
        problem_data = problem.problem.model_dump()

        try:
            # Upload the problem to S3
            bucket_path = upload_problem_to_s3(problem_id, problem_data)

            # Update the problem with the bucket path
            new_problem.bucket_path = bucket_path
            await db.commit()
            await db.refresh(new_problem)

            problem_logger.info(f"Problem uploaded to bucket: {bucket_path}")
        except Exception as s3_error:
            problem_logger.error(f"Error uploading problem to S3: {str(s3_error)}")
            # Continue even if S3 upload fails, as we've already created the problem in the database
            # In a production environment, you might want to roll back the transaction or implement a retry mechanism

        problem_logger.info(f"Problem created successfully: ID {new_problem.id}")
        return new_problem
    except SQLAlchemyError as db_error:
        problem_logger.error(f"Database error creating problem: {str(db_error)}")
        raise DatabaseException(detail="Failed to create problem due to database error")
    except Exception as e:
        problem_logger.error(f"Unexpected error creating problem: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while creating the problem"
        )


@problem_router.post("/get", response_model=ProblemResponse)
async def get_problem(
    problem_id: uuid.UUID,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Get a problem by ID.
    """
    problem_logger.info(f"Getting problem: ID {problem_id}")

    try:
        result = await db.execute(select(Problem).where(Problem.id == problem_id))
        problem = result.scalars().first()

        if not problem:
            problem_logger.warning(f"Problem not found: ID {problem_id}")
            raise ResourceNotFoundException(detail="Problem not found")

        problem_logger.info(f"Problem retrieved successfully: ID {problem_id}")
        return problem
    except ResourceNotFoundException:
        raise
    except SQLAlchemyError as db_error:
        problem_logger.error(f"Database error retrieving problem: {str(db_error)}")
        raise DatabaseException(
            detail="Failed to retrieve problem due to database error"
        )
    except Exception as e:
        problem_logger.error(f"Unexpected error retrieving problem: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while retrieving the problem"
        )


@problem_router.put("/update", response_model=ProblemResponse)
async def update_problem(
    problem_id: uuid.UUID,
    problem_update: ProblemUpdate,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Update a problem.
    """
    problem_logger.info(f"Updating problem: ID {problem_id}")

    try:
        result = await db.execute(select(Problem).where(Problem.id == problem_id))
        problem = result.scalars().first()

        if not problem:
            problem_logger.warning(f"Problem not found: ID {problem_id}")
            raise ResourceNotFoundException(detail="Problem not found")

        # Update fields if provided
        update_data = problem_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(problem, key, value)

        problem.updated_at = datetime.now()

        await db.commit()
        await db.refresh(problem)

        problem_logger.info(f"Problem updated successfully: ID {problem_id}")
        return problem
    except ResourceNotFoundException:
        raise
    except SQLAlchemyError as db_error:
        problem_logger.error(f"Database error updating problem: {str(db_error)}")
        raise DatabaseException(detail="Failed to update problem due to database error")
    except Exception as e:
        problem_logger.error(f"Unexpected error updating problem: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while updating the problem"
        )


@problem_router.delete("/delete")
async def delete_problem(
    problem_id: uuid.UUID,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Delete a problem.
    """
    problem_logger.info(f"Deleting problem: ID {problem_id}")

    try:
        result = await db.execute(select(Problem).where(Problem.id == problem_id))
        problem = result.scalars().first()

        if not problem:
            problem_logger.warning(f"Problem not found: ID {problem_id}")
            raise ResourceNotFoundException(detail="Problem not found")

        await db.delete(problem)
        await db.commit()

        problem_logger.info(f"Problem deleted successfully: ID {problem_id}")
        return {"message": f"Problem {problem_id} deleted successfully"}
    except ResourceNotFoundException:
        raise
    except SQLAlchemyError as db_error:
        problem_logger.error(f"Database error deleting problem: {str(db_error)}")
        raise DatabaseException(detail="Failed to delete problem due to database error")
    except Exception as e:
        problem_logger.error(f"Unexpected error deleting problem: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while deleting the problem"
        )


@problem_router.get("/", response_model=List[ProblemResponse])
async def list_problems(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    List all problems with pagination.
    """
    problem_logger.info(f"Listing problems: skip={skip}, limit={limit}")

    try:
        result = await db.execute(select(Problem).offset(skip).limit(limit))
        problems = result.scalars().all()

        problem_logger.info(f"Retrieved {len(problems)} problems")
        return problems
    except SQLAlchemyError as db_error:
        problem_logger.error(f"Database error listing problems: {str(db_error)}")
        raise DatabaseException(detail="Failed to list problems due to database error")
    except Exception as e:
        problem_logger.error(f"Unexpected error listing problems: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while listing problems"
        )
