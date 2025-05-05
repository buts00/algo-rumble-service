import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import logger
from src.db.main import get_session
from src.errors import DatabaseException, ResourceNotFoundException
from src.problem.models.problem import Problem
from src.problem.schemas.problem import (ProblemCreate, ProblemResponse,
                                         ProblemUpdate)

# Create a module-specific logger
problem_logger = logger.getChild("problem")

problem_router = APIRouter(prefix="/problems", tags=["problems"])


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
        new_problem = Problem(
            rating=problem.rating,
            topics=problem.topics,
            bucket_path=problem.bucket_path,
        )

        db.add(new_problem)
        await db.commit()
        await db.refresh(new_problem)

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


@problem_router.get("/{problem_id}", response_model=ProblemResponse)
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


@problem_router.put("/{problem_id}", response_model=ProblemResponse)
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


@problem_router.delete("/{problem_id}")
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
