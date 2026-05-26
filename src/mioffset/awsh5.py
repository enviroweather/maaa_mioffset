# experimental/WIP hdf5 reader from s3
# uses yield so need to get all data right away 
# from the H5 file and then returning
# so that the tmp_path can be released

import tempfile, os, h5py
from .aws import S3Client, ClientError


def read_hdf5_from_s3(s3_client:S3Client, bucket:str, filename:str):
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