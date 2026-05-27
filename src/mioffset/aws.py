# reload .env file to accommodate changes during development
import logging

from dotenv import load_dotenv
from os import getenv
# aws 
import boto3
from types_boto3_s3.client import S3Client
from botocore.exceptions import ClientError

def get_aws_config(dotenv_file:str|None = None)->dict[str, str]:
    """Read AWS-related environment values after loading dotenv.

    This helper is informational and supports local development. Runtime
    credentials for AWS calls should come from boto3's default provider chain.

    Args:
        dotenv_file (str | None, optional): path to dot env file. Defaults to None which will look for default (.env)

    Returns:
        dict[str, str]: AWS-related environment configuration.
    """
    
    
    # load dotenv properly deals with None value for dotenv file
    load_dotenv(dotenv_path = dotenv_file,override = True)
    
    # note region name is optional and will use system config'd region
    aws_config = { 
        "aws_profile" : getenv("AWS_PROFILE", ""),
        "aws_access_key_id" : getenv("AWS_ACCESS_KEY_ID", ""), 
        "aws_secret_access_key" : getenv("AWS_SECRET_ACCESS_KEY", ""), 
        "aws_session_token" : getenv("AWS_SESSION_TOKEN", ""),
        "region_name" : getenv("REGION_NAME", "") 
    }

    return aws_config


def get_s3_client(aws_config:dict|None = None, dotenv_file:str|None = None, region_name:str|None = None)->S3Client:
    """Get an S3 client using boto3's default credential provider chain.

    This avoids passing raw access keys and works in both local environments
    (profiles/shared config) and AWS Lambda (execution role credentials).

    Args:
        aws_config (dict | None, optional): optional config dict that may include
            ``aws_profile`` and/or ``region_name``. Raw keys are ignored.
        dotenv_file (str | None, optional): path to dot env file. Defaults to None which will look for default (.env)
        region_name (str | None, optional): optional AWS region override.

    Returns:
        S3Client: Boto3 client for accessing S3 storage (only, no other services)
    """
    aws_config_dict:dict = aws_config or get_aws_config(dotenv_file)
    profile_name = aws_config_dict.get("aws_profile") or getenv("AWS_PROFILE") or None
    resolved_region = region_name or aws_config_dict.get("region_name") or getenv("REGION_NAME") or None

    if profile_name:
        session = boto3.Session(profile_name=profile_name, region_name=resolved_region)
    else:
        session = boto3.Session(region_name=resolved_region)

    s3_client = session.client('s3')
    return(s3_client)


def check_s3_client(s3_client:S3Client):
    """Validate that an object looks like a usable S3 client.

    This is a structural check and intentionally does not call AWS APIs,
    because roles may lack ``ListBuckets`` permission while still being valid
    for bucket-scoped access.

    Args:
        s3_client (S3Client): valid boto 3 S3 client.

    Returns:
        bool: True if client is valid, False otherwise
    """

    required_methods = ("head_bucket", "get_object", "download_file")
    for method_name in required_methods:
        if not hasattr(s3_client, method_name):
            raise TypeError(f"Invalid S3 client (missing {method_name} method)")

    return True


def check_bucket(s3_client:S3Client, bucket_name:str):
    """is the bucket a thing?

    Args:
        s3_client (S3Client): valid boto 3 S3 client.   
        bucket_name (str): name of bucket to check for

    Returns:
        bool: True if bucket exists, False otherwise
    """
    
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError:
        logging.error(f"Bucket {bucket_name} does not exist or is not accessible")
        raise
    
