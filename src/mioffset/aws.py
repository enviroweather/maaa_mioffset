# reload .env file to accommodate changes during development
from dotenv import load_dotenv
from os import getenv
# aws 
import boto3
import botocore
from types_boto3_s3.client import S3Client
from botocore.exceptions import ClientError

def get_aws_config(dotenv_file = None):
    
    # load env and get the very latest
    if dotenv_file:
        load_dotenv(dotenv_file,override = True)
    else:
        load_dotenv(override = True)

    # note region name is optional and will use system config'd region
    aws_config = { 
        "aws_access_key_id" : getenv("AWS_ACCESS_KEY_ID"), 
        "aws_secret_access_key" : getenv("AWS_SECRET_ACCESS_KEY"), 
        "region_name" : getenv("REGION_NAME") 
    }

    if aws_config["aws_access_key_id"] is None:
        raise ValueError("AWS_ACCESS_KEY_ID is not set in environment or .env file")
    if aws_config["aws_secret_access_key"] is None:
        raise ValueError("AWS_SECRET_ACCESS_KEY is not set in environment or .env file")

    return aws_config


def get_s3_client(aws_config:dict|None = None)->S3Client:
    aws_config:dict = aws_config or get_aws_config()
    session = boto3.Session(**aws_config)
    s3_client = session.client('s3')
    return(s3_client)


def check_bucket(s3_client:S3Client, bucket_name):
    
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket {bucket_name} exists")
        return True
    except ClientError:
        print(f"Bucket {bucket_name} does not exist or is not accessible")
        return False
    
# experimental/WIP hdf5 reader from s3
# uses yield so need to get all data right away 
# from the H5 file and then returning
# so that the tmp_path can be released
def read_hdf5_from_s3(s3_client:S3Client, bucket, filename):
    import tempfile, os, h5py
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.h5')
    os.close(tmp_fd)
    try:
        s3_client.download_file(bucket, filename, tmp_path)
        with h5py.File(tmp_path, 'r') as hf:
            yield hf
    except ClientError as e:
        raise RuntimeError(
            f"could not get H5 file from S3 {bucket}/{filename}: {e}"
        )
    except Exception as e:
        raise RuntimeError(f"could not get H5 file from S3 {bucket}/{filename}: {e}")
    finally:
        os.unlink(tmp_path)