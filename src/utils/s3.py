import json
from typing import Any, Dict

import boto3
from botocore.client import Config

from src.config import Config as AppConfig


def get_s3_client():
    """
    Create and return an S3 client configured for DigitalOcean Spaces.
    """
    session = boto3.session.Session()
    return session.client(
        "s3",
        region_name="fra1",  # Frankfurt region
        endpoint_url="https://fra1.digitaloceanspaces.com",
        aws_access_key_id=AppConfig.DIGITAL_OCEAN_ACCESS_KEY_ID,
        aws_secret_access_key=AppConfig.DIGITAL_OCEAN_API_KEY,
        config=Config(signature_version="s3v4"),
    )


def upload_problem_to_s3(problem_id: str, problem_data: Dict[str, Any]) -> str:
    """
    Upload problem data to DigitalOcean Spaces.

    Args:
        problem_id: The ID of the problem
        problem_data: The problem data to upload

    Returns:
        The path to the uploaded file in the bucket
    """
    s3_client = get_s3_client()

    # Convert problem data to JSON
    problem_json = json.dumps(problem_data)

    # Upload to DigitalOcean Spaces
    bucket_name = AppConfig.DIGITAL_OCEAN_BUCKET_NAME
    file_path = f"problems/{problem_id}.json"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=file_path,
        Body=problem_json,
        ACL="public-read",
        ContentType="application/json",
    )

    return file_path


def upload_testcase_to_s3(
    problem_id: str, testcase_number: int, input_data: str, output_data: str
) -> Dict[str, str]:
    """
    Upload testcase input and output to DigitalOcean Spaces.

    Args:
        problem_id: The ID of the problem
        testcase_number: The number of the testcase
        input_data: The input data for the testcase
        output_data: The expected output for the testcase

    Returns:
        Dictionary with paths to the uploaded input and output files
    """
    s3_client = get_s3_client()
    bucket_name = AppConfig.DIGITAL_OCEAN_BUCKET_NAME

    # Upload input file
    input_path = f"tests/{problem_id}/{testcase_number}.in"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=input_path,
        Body=input_data,
        ACL="public-read",
        ContentType="text/plain",
    )

    # Upload output file
    output_path = f"tests/{problem_id}/{testcase_number}.out"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=output_path,
        Body=output_data,
        ACL="public-read",
        ContentType="text/plain",
    )

    return {"input_path": input_path, "output_path": output_path}
