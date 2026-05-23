# reload .env file to accommodate changes during development
from dotenv import load_dotenv
from os import getenv
# aws 
import boto3
import botocore
import h5py
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
        print(f"Bucket {bucket_name} exists")
        return True
    except ClientError:
        print(f"Bucket {bucket_name} does not exist or is not accessible")
        return False
    
# experimental/WIP hdf5 reader from s3
# uses yield so need to get all data right away 
# from the H5 file and then returning
# so that the tmp_path can be released
def read_hdf5_from_s3(s3_client:S3Client, bucket:str, filename:str)->h5py.File:
    """since hdf5 can only be read properly from disk, this enables
    reading from S3 via a temporary local file.  Uses a generator in order to 
    have the tempfile closed and deleted when reading is complete. 
 
    Args:
        s3_client (S3Client): valid Boto3 S3 client
        bucket (str): name of the S3 bucket
        filename (str): name of the HDF5 file in the bucket

    Raises:
        RuntimeError:  raised if there is a client / AWS error
        RuntimeError: _description_

    Yields:
        _type_: _description_
    """
    
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