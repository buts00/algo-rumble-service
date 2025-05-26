import boto3
import requests
from botocore.exceptions import ClientError
from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config, logger
from src.data.schemas import Match, Problem, User
from src.errors import ResourceNotFoundException

# Create a module-specific logger
submission_logger = logger.getChild("submission")


async def get_match_by_id(db: AsyncSession, match_id: UUID4) -> Match:
    """
    Get a match by ID from the database.
    """
    try:
        result = await db.execute(select(Match).where(Match.id == match_id))
        match = result.scalars().first()
        if not match:
            submission_logger.warning(f"Match not found: ID {match_id}")
            raise ResourceNotFoundException(detail="Match not found")
        return match
    except Exception as e:
        submission_logger.error(f"Error retrieving match {match_id}: {str(e)}")
        raise


async def get_problem_by_id(db: AsyncSession, problem_id: str) -> Problem:
    """
    Get a problem by ID from the database.
    """
    try:
        result = await db.execute(select(Problem).where(Problem.id == problem_id))
        problem = result.scalars().first()
        if not problem:
            submission_logger.warning(f"Problem not found: ID {problem_id}")
            raise ResourceNotFoundException(detail="Problem not found")
        return problem
    except Exception as e:
        submission_logger.error(f"Error retrieving problem {problem_id}: {str(e)}")
        raise


async def get_users_by_ids(db: AsyncSession, user_ids: list[str]) -> list[User]:
    """
    Get users by their IDs from the database.
    """
    try:
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users = result.scalars().all()
        return users
    except Exception as e:
        submission_logger.error(f"Error retrieving users {user_ids}: {str(e)}")
        raise


def fetch_test_cases(problem_id: str) -> list[dict]:
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


async def check_solution(code: str, language: str, test_cases: list[dict]) -> bool:
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
