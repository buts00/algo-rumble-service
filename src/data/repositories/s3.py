import json
from typing import Any, Dict

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from src.config import Config as AppConfig
from src.config import logger

s3_logger = logger.getChild("s3")


def get_s3_client():
    """Create and return a synchronous S3 client for DigitalOcean Spaces."""
    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=AppConfig.AWS_ENDPOINT_URL,
        region_name=AppConfig.AWS_REGION,
        aws_access_key_id=AppConfig.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AppConfig.AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )


async def upload_problem_to_s3(problem_id: str, problem_data: Dict[str, Any]) -> str:
    s3_client = get_s3_client()
    try:
        s3_logger.debug(f"Problem data type: {type(problem_data)}, data: {problem_data}")
        problem_json = json.dumps(problem_data)
        bucket_name = AppConfig.AWS_BUCKET_NAME
        file_path = f"problems/{problem_id}.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_path,
            Body=problem_json,
            ACL="public-read",
            ContentType="application/json",
        )
        s3_logger.info(f"Uploaded problem {problem_id} to {file_path}")
        return file_path
    except ClientError as e:
        s3_logger.error(f"Error uploading problem {problem_id} to S3: {str(e)}")
        raise
    except TypeError as e:
        s3_logger.error(f"Serialization error for problem {problem_id}: {str(e)}")
        raise


async def upload_testcase_to_s3(
    problem_id: str, testcase_number: int, input_data: str, output_data: str
) -> Dict[str, str]:
    """Upload testcase input and output to DigitalOcean Spaces."""
    s3_client = get_s3_client()
    bucket_name = AppConfig.AWS_BUCKET_NAME
    try:
        input_path = f"tests/{problem_id}/{testcase_number}.in"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=input_path,
            Body=input_data,
            ACL="public-read",
            ContentType="text/plain",
        )
        output_path = f"tests/{problem_id}/{testcase_number}.out"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=output_path,
            Body=output_data,
            ACL="public-read",
            ContentType="text/plain",
        )
        s3_logger.info(f"Uploaded testcase {testcase_number} for problem {problem_id}")
        return {"input_path": input_path, "output_path": output_path}
    except ClientError as e:
        s3_logger.error(
            f"Error uploading testcase {testcase_number} for problem {problem_id}: {str(e)}"
        )
        raise
