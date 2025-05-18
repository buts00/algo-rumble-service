import uuid
from datetime import datetime
from typing import List

import boto3
import requests
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.data.schemas import User
from src.config import Config, logger
from src.data.repositories import get_session
from src.errors import (
    AuthorizationException,
    BadRequestException,
    DatabaseException,
    ResourceNotFoundException,
)
from src.data.schemas import Match, MatchStatus
from src.business.services import update_ratings_after_match, send_match_notification
from src.data.schemas import Problem
from src.data.schemas import SubmissionCreate

# Create a module-specific logger
submission_logger = logger.getChild("submission")

submission_router = APIRouter(prefix="/submissions", tags=["submissions"])


@submission_router.post("/match")
async def submit_solution(
    submission_data: SubmissionCreate,
    db: Session = Depends(get_session),
    request: Request = None,
):
    """
    Submit a solution for a match.
    The solution is run against test cases from Digital Ocean using the OneCompiler API.
    If the solution is correct, the match ends instantly and the player who submitted the solution wins.
    Player ratings are updated accordingly.
    """
    match_id = str(submission_data.match_id)
    user_id = str(submission_data.user_id)
    code = submission_data.code
    language = submission_data.language

    submission_logger.info(
        f"Solution submission: Match ID {match_id}, User ID {user_id}, Language: {language}"
    )

    try:
        # Convert user_id to UUID
        try:
            user_uuid = uuid.UUID(user_id)
            match_uuid = uuid.UUID(match_id)
        except ValueError:
            submission_logger.warning(
                f"Solution submission failed: Invalid user ID format: {user_id}"
            )
            raise ResourceNotFoundException(detail="User not found")

        # Get the match
        result = await db.execute(select(Match).where(Match.id == match_uuid))
        match = result.scalars().first()

        if not match:
            submission_logger.warning(
                f"Solution submission failed: Match not found: ID {match_id}"
            )
            raise ResourceNotFoundException(detail="Match not found")

        # Check if user is part of the match
        if match.player1_id != user_uuid and match.player2_id != user_uuid:
            submission_logger.warning(
                f"Solution submission failed: User not in match: User ID {user_uuid}, "
                f"Match ID {match_id}"
            )
            raise AuthorizationException(
                detail="Not authorized to submit solution for this match"
            )

        # Check if match is active
        if match.status != MatchStatus.ACTIVE:
            submission_logger.warning(
                f"Solution submission failed: Match not active: ID {match_id}, "
                f"Status {match.status}"
            )
            raise BadRequestException(detail="Match is not active")

        # Get the problem associated with the match
        if not match.problem_id:
            submission_logger.warning(
                f"Solution submission failed: No problem associated with match: ID {match_id}"
            )
            raise BadRequestException(detail="No problem associated with this match")

        problem_result = await db.execute(
            select(Problem).where(Problem.id == match.problem_id)
        )
        problem = problem_result.scalars().first()

        if not problem:
            submission_logger.warning(
                f"Solution submission failed: Problem not found: ID {match.problem_id}"
            )
            raise ResourceNotFoundException(detail="Problem not found")

        # Fetch test cases from Digital Ocean
        test_cases = fetch_test_cases(problem.id)
        if not test_cases:
            submission_logger.warning(
                f"Solution submission failed: No test cases found for problem: ID {match.problem_id}"
            )
            raise BadRequestException(detail="No test cases found for this problem")

        # Run the solution against test cases using OneCompiler API
        is_correct = await check_solution(code, language, test_cases)

        # If solution is correct, end the match and update ratings
        if is_correct:
            match.status = MatchStatus.COMPLETED
            match.winner_id = user_uuid
            match.end_time = datetime.now()

            # Get both players
            player1_result = await db.execute(
                select(User).where(User.id == match.player1_id)
            )
            player1 = player1_result.scalars().first()

            player2_result = await db.execute(
                select(User).where(User.id == match.player2_id)
            )
            player2 = player2_result.scalars().first()

            # Update ratings
            if player1 and player2:
                winner = player1 if match.winner_id == player1.id else player2
                loser = player2 if match.winner_id == player1.id else player1

                await update_ratings_after_match(db, winner.id, loser.id)
                db.commit()

                submission_logger.info(
                    f"Ratings updated: Winner {winner.username} ({winner.rating}), "
                    f"Loser {loser.username} ({loser.rating})"
                )

                # Send match completion notification to both players
                winner_notification = {
                    "type": "match_completed",
                    "message": "Congratulations! You solved the problem correctly and won the match.",
                    "match_id": str(match.id),
                    "problem_id": str(match.problem_id),
                    "result": "win",
                    "new_rating": winner.rating,
                }
                await send_match_notification(str(winner.id), winner_notification)

                loser_notification = {
                    "type": "match_completed",
                    "message": f"Your opponent '{winner.username}' solved the problem and won the match.",
                    "match_id": str(match.id),
                    "problem_id": str(match.problem_id),
                    "result": "loss",
                    "new_rating": loser.rating,
                }
                await send_match_notification(str(loser.id), loser_notification)

            submission_logger.info(
                f"Match completed: ID {match_id}, Winner: {user_uuid}"
            )
            return {"is_correct": True, "message": "Solution correct, match completed"}
        else:
            # Notify user about incorrect solution
            await send_match_notification(
                user_id,
                {
                    "type": "submission_result",
                    "is_correct": False,
                    "message": "Incorrect solution. Try again!",
                    "match_id": match_id,
                    "problem_id": str(match.problem_id),
                },
            )
            submission_logger.info(
                f"Incorrect solution submitted: Match ID {match_id}, User ID {user_uuid}"
            )
            return {
                "is_correct": False,
                "message": "Solution incorrect, match continues",
            }

    except (ResourceNotFoundException, AuthorizationException, BadRequestException):
        raise
    except SQLAlchemyError as db_error:
        submission_logger.error(f"Database error during submission: {str(db_error)}")
        raise DatabaseException(
            detail="Failed to process submission due to database error"
        )
    except Exception as e:
        submission_logger.error(f"Unexpected error during submission: {str(e)}")
        raise DatabaseException(
            detail="An unexpected error occurred while processing the submission"
        )


def fetch_test_cases(problem_id: str) -> List[dict]:
    """
    Fetch all test cases by listing the test folder and pairing .in/.out files.

    Args:
        problem_id: The id of the problem

    Returns:
        A list of test cases with input and expected output
    """
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{Config.AWS_REGION}.digitaloceanspaces.com",
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )

    prefix = f"tests/{problem_id}/"
    bucket_name = Config.AWS_BUCKET_NAME
    test_cases = []

    try:
        # 1. List all files in the folder
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        files = response.get("Contents", [])

        # 2. Create set of file names (e.g., "01.in", "01.out")
        file_keys = {f["Key"].replace(prefix, "") for f in files}
        input_files = {f[:-3] for f in file_keys if f.endswith(".in")}
        output_files = {f[:-4] for f in file_keys if f.endswith(".out")}

        # 3. Get all valid test indices that have both .in and .out
        valid_indices = sorted(input_files & output_files)

        for idx in valid_indices:
            try:
                input_obj = s3.get_object(Bucket=bucket_name, Key=f"{prefix}{idx}.in")
                output_obj = s3.get_object(Bucket=bucket_name, Key=f"{prefix}{idx}.out")

                input_data = input_obj["Body"].read().decode("utf-8")
                output_data = output_obj["Body"].read().decode("utf-8")

                test_cases.append({"input": input_data, "expected_output": output_data})

            except ClientError as e:
                submission_logger.warning(f"Failed to fetch test case {idx}: {str(e)}")

        submission_logger.info(
            f"Fetched {len(test_cases)} test cases for problem {problem_id}"
        )
        return test_cases

    except Exception as e:
        submission_logger.error(f"Error fetching test cases: {str(e)}")
        return []


async def check_solution(code: str, language: str, test_cases: List[dict]) -> bool:
    """
    Check if a solution is correct by running it against test cases using the OneCompiler API.

    Args:
        code: The solution code
        language: The programming language
        test_cases: A list of test cases, each containing input and expected output

    Returns:
        True if the solution passes all test cases, False otherwise
    """
    try:
        # OneCompiler API endpoint and headers
        url = f"https://{Config.ONECOMPILER_API_HOST}/api/v1/run"
        headers = {
            "x-rapidapi-key": Config.ONECOMPILER_API_KEY,
            "x-rapidapi-host": Config.ONECOMPILER_API_HOST,
            "Content-Type": "application/json",
        }

        # Check each test case
        for i, test_case in enumerate(test_cases):
            payload = {
                "language": language,
                "stdin": test_case["input"],
                "files": [
                    {
                        "name": f"solution.{get_file_extension(language)}",
                        "content": code,
                    }
                ],
            }

            submission_logger.info(f"Running test case {i + 1}/{len(test_cases)}")
            response = requests.post(url, json=payload, headers=headers)

            if response.status_code != 200:
                submission_logger.error(
                    f"OneCompiler API error: {response.status_code} - {response.text}"
                )
                return False

            result = response.json()

            # Check if there was an error during execution
            if result.get("error"):
                submission_logger.debug(
                    f"Solution failed on test case {i + 1}: Execution error"
                )
                return False

            # Check if the output matches the expected output
            actual_output = result.get("stdout", "").strip()
            expected_output = test_case["expected_output"].strip()

            if actual_output != expected_output:
                submission_logger.info(
                    f"Solution failed on test case {i + 1}: Output mismatch"
                )
                submission_logger.debug(
                    f"Expected: '{expected_output}', Actual: '{actual_output}'"
                )
                return False

        # If we get here, all test cases passed
        submission_logger.info("Solution passed all test cases")
        return True
    except Exception as e:
        submission_logger.error(f"Error checking solution: {str(e)}")
        return False


def get_file_extension(language: str) -> str:
    """
    Get the file extension for a programming language.

    Args:
        language: The programming language

    Returns:
        The file extension for the language
    """
    extensions = {
        "python": "py",
        "javascript": "js",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "csharp": "cs",
        "go": "go",
        "ruby": "rb",
        "rust": "rs",
        "swift": "swift",
        "typescript": "ts",
        "kotlin": "kt",
        "scala": "scala",
        "php": "php",
    }
    return extensions.get(language.lower(), "txt")
