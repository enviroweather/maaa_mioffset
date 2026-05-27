# reload .env file to accommodate changes during development
import logging
from typing import Generator

from dotenv import load_dotenv
from os import getenv
import sys
# aws 
import boto3
from types_boto3_s3.client import S3Client
from botocore.exceptions import ClientError

def get_aws_config(dotenv_file:str|None = None)->dict[str, str]:
    """get the configuration for AWS client use from the environment.  allows for using 
    different dot-env env config files

    Args:
        dotenv_file (str | None, optional): path to dot env file. Defaults to None which will look for default (.env)

    Raises:
        ValueError: if the required access key id value is not set
        ValueError: if the required secret access key value is not set

    Returns:
        dict[str, str]: AWS configuration dictionary need to create a client
    """
    
    
    # load dotenv properly deals with None value for dotenv file
    load_dotenv(dotenv_path = dotenv_file,override = True)
    
    # note region name is optional and will use system config'd region
    aws_config = { 
        "aws_access_key_id" : getenv("AWS_ACCESS_KEY_ID", ""), 
        "aws_secret_access_key" : getenv("AWS_SECRET_ACCESS_KEY", ""), 
        "region_name" : getenv("REGION_NAME", "") 
    }

    if aws_config["aws_access_key_id"] is None:
        raise ValueError("AWS_ACCESS_KEY_ID is not set in environment or .env file")
    if aws_config["aws_secret_access_key"] is None:
        raise ValueError("AWS_SECRET_ACCESS_KEY is not set in environment or .env file")
    if aws_config["region_name"] is None:
        raise ValueError("REGION_NAME is not set in environment or .env file")

    return aws_config


def get_s3_client(aws_config:dict|None = None, dotenv_file:str|None = None)->S3Client:
    """get a client for working with AWS S3 storage

    Args:
        aws_config (dict | None, optional): aws config, if not provided, will be loaded from dotenv file. Defaults to None.
        dotenv_file (str | None, optional): path to dot env file. Defaults to None which will look for default (.env)

    Returns:
        S3Client: Boto3 client for accessing S3 storage (only, no other services)
    """
    aws_config_dict:dict = aws_config or get_aws_config(dotenv_file)
    session = boto3.Session(**aws_config_dict)
    s3_client = session.client('s3')
    return(s3_client)


def check_s3_client(s3_client:S3Client):
    """validate the S3 client

    Args:
        s3_client (S3Client): valid boto 3 S3 client.

    Returns:
        bool: True if client is valid, False otherwise
    """
    
    if not hasattr(s3_client, "list_buckets"):
        logging.error("Invalid S3 client (missing list_buckets method)")
        return False
    
    try:
        s3_client.list_buckets()
        return True
    except ClientError:
        logging.error("Failed to validate S3 client")
        raise


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
    
