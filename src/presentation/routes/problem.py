import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger
from src.data.repositories import get_session
from src.data.repositories.problem import (
    create_problem_in_db,
    create_testcases_in_db,
    delete_problem_from_db,
    get_problem_by_id,
    update_problem_in_db,
)
from src.data.schemas import ProblemCreate, ProblemResponse, ProblemUpdate, TestCaseCreate, TestCaseResponse

problem_logger = logger.getChild("problem")
problem_router = APIRouter(prefix="/problems", tags=["problems"])
testcase_router = APIRouter(prefix="/testcases", tags=["testcases"])


@testcase_router.post(
    "/",
    response_model=TestCaseResponse,
    summary="Create test cases",
    description="Creates test cases for a problem and uploads them to DigitalOcean Spaces."
)
async def create_testcases(
    testcase_data: TestCaseCreate,
    db: AsyncSession = Depends(get_session),
):
    """Create test cases for a problem and upload them to DigitalOcean Spaces."""
    testcases = [{"input": tc.input, "output": tc.output} for tc in testcase_data.testcases]
    problem_logger.info(f"Creating {len(testcases)} testcases for problem ID: {testcase_data.problem_id}")
    return await create_testcases_in_db(db, testcase_data.problem_id, testcases)


@problem_router.post(
    "/",
    response_model=ProblemResponse,
    summary="Create a problem",
    description="Creates a new problem with metadata and uploads it to DigitalOcean Spaces."
)
async def create_problem(
    problem_data: ProblemCreate,
    db: AsyncSession = Depends(get_session),
):
    """Create a new problem and store it in DigitalOcean Spaces."""
    problem_logger.info(f"Creating problem with rating: {problem_data.rating}")
    return await create_problem_in_db(db, problem_data)


@problem_router.get(
    "/{problem_id}",
    response_model=ProblemResponse,
    summary="Get a problem",
    description="Retrieves a problem by its ID."
)
async def get_problem(
    problem_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Retrieve a problem by its unique ID."""
    problem_logger.info(f"Fetching problem ID: {problem_id}")
    return await get_problem_by_id(db, problem_id)


@problem_router.put(
    "/{problem_id}",
    response_model=ProblemResponse,
    summary="Update a problem",
    description="Updates a problem's metadata or content."
)
async def update_problem(
    problem_id: uuid.UUID,
    problem_update: ProblemUpdate,
    db: AsyncSession = Depends(get_session),
):
    """Update an existing problem with new metadata or content."""
    update_data = problem_update.model_dump(exclude_unset=True)
    problem_logger.info(f"Updating problem ID: {problem_id}")
    return await update_problem_in_db(db, problem_id, update_data)


@problem_router.delete(
    "/{problem_id}",
    summary="Delete a problem",
    description="Deletes a problem and its associated data from DigitalOcean Spaces."
)
async def delete_problem(
    problem_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Delete a problem and its associated data."""
    problem_logger.info(f"Deleting problem ID: {problem_id}")
    return await delete_problem_from_db(db, problem_id)


@problem_router.get(
    "/",
    response_model=List[ProblemResponse],
    summary="List problems",
    description="Lists all problems with pagination."
)
async def list_problems(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_session),
):
    """
    List all problems with pagination.
    TODO: Implement list_problems_from_db in src/data/repositories/problem.py.
    """
    problem_logger.info(f"Listing problems with skip: {skip}, limit: {limit}")
    problem_logger.warning("list_problems_from_db not implemented, returning empty list")
    return []