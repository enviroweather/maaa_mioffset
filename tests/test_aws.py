"""
tests/test_py

Tests for py.

All tests assume valid AWS credentials and NARR_BUCKET are present in the
.env file (loaded by conftest.py before any tests run).
"""

import os
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

from mioffset.aws import *


class TestGetAwsConfig:
    # ensure config is a dict for type checks
    config: dict = get_aws_config()

    def test_returns_dict(self):        
        assert isinstance(self.config, dict)

    def test_has_required_keys(self):       
        assert "aws_profile" in self.config
        assert "aws_access_key_id" in self.config
        assert "aws_secret_access_key" in self.config
        assert "aws_session_token" in self.config
        assert "region_name" in self.config

    def test_values_are_strings(self):
        for value in self.config.values():
            assert isinstance(value, str)

    def test_empty_values_are_allowed(self):
        # Lambda and local profile-based setups can work with no raw key values.
        assert self.config["aws_access_key_id"] is not None
        assert self.config["aws_secret_access_key"] is not None


class TestGetS3Client:
    def test_returns_s3_client(self):
        client = get_s3_client()
        assert client is not None

    def test_client_has_head_bucket(self):
        client = get_s3_client()
        assert hasattr(client, "head_bucket")

    def test_client_has_get_object(self):
        client = get_s3_client()
        assert hasattr(client, "get_object")

    def test_accepts_config_with_region(self):
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

    def test_nonexistent_bucket_raises_client_error(self, s3_client):
        with pytest.raises(ClientError):
            check_bucket(s3_client, "this-bucket-should-not-exist-mioffset-xyz-999")


class TestCheckS3Client:
    def test_raises_type_error_for_non_client_object(self):
        with pytest.raises(TypeError, match="Invalid S3 client"):
            check_s3_client(object())

    def test_returns_true_for_mock_client_with_required_methods(self):
        mock_s3 = MagicMock()
        mock_s3.head_bucket = MagicMock()
        mock_s3.get_object = MagicMock()
        mock_s3.download_file = MagicMock()
        assert check_s3_client(mock_s3) is True

    def test_returns_true_for_real_client(self):
        client = get_s3_client()
        assert check_s3_client(client) is True
