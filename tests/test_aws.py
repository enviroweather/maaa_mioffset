"""
tests/test_py

Tests for py.

All tests assume valid AWS credentials and BUCKET_NAME are present in the
.env file (loaded by conftest.py before any tests run).
"""

import os
import pytest
import boto3

from aws import *


class TestGetAwsConfig:
    # ensure config is a dict for type checks
    config: dict = get_aws_config()

    def test_returns_dict(self):        
        assert isinstance(self.config, dict)

    def test_has_required_keys(self):       
        assert "aws_access_key_id" in self.config
        assert "aws_secret_access_key" in self.config
        assert "region_name" in self.config

    def test_credentials_not_none(self):
        assert self.config["aws_access_key_id"] is not None
        assert self.config["aws_secret_access_key"] is not None

    def test_credentials_are_strings(self):
        assert isinstance(self.config["aws_access_key_id"], str)
        assert isinstance(self.config["aws_secret_access_key"], str)

    def test_credentials_nonempty(self):
        assert len(self.config["aws_access_key_id"]) > 0
        assert len(self.config["aws_secret_access_key"]) > 0


class TestGetS3Client:
    def test_returns_s3_client(self):
        client = get_s3_client()
        assert client is not None

    def test_client_has_list_buckets(self):
        client = get_s3_client()
        assert hasattr(client, "list_buckets")

    def test_can_list_buckets(self):
        """Verify the credentials actually authenticate against AWS."""
        client = get_s3_client()
        response = client.list_buckets()
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_accepts_explicit_config(self):
        config = get_aws_config()
        client = get_s3_client(aws_config=config)
        assert client is not None


class TestCheckBucket:
    @pytest.fixture
    def s3_client(self):
        return get_s3_client()

    @pytest.fixture
    def bucket_name(self):
        name = os.getenv("NARR_BUCKET")
        if not name:
            pytest.skip("NARR_BUCKET not set in .env")
        return name

    def test_returns_true_for_valid_bucket(self, s3_client, bucket_name):
        assert check_bucket(s3_client, bucket_name) is True

    def test_returns_false_for_nonexistent_bucket(self, s3_client):
        assert check_bucket(s3_client, "this-bucket-should-not-exist-mioffset-xyz-999") is False
