"""
tests/test_mioffset.py

Tests for functions in mioffset/mioffset.py.

Goal: verify that build_fod_response() returns a dict that can be
serialized to JSON, suitable for use as an API response.

Test structure
--------------
Pure unit tests (always run, no external resources needed):
  - TestConfigFromEnv     — config_from_env() reads env vars correctly
  - TestBuildFodResponse  — build_fod_response() returns JSON-serializable dict
                            NOTE: two bugs currently prevent these from passing:
                              1. `topt` is referenced but never defined in
                                 build_fod_response() → NameError
                              2. plot SVG is encoded to bytes before being placed
                                 in the response dict → not JSON-serializable
                            Fix those bugs and the tests will pass.

Integration tests (@pytest.mark.integration):
  Skipped automatically when AWS credentials or NARR_BUCKET are absent.
  - TestFodRunS3   — fod_run_s3() with real S3 data
  - TestApiHandler — api_handler() end-to-end

Run only fast tests:
    pytest -m "not integration"

Run all tests (including live S3):
    pytest
"""

import json
import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from conftest import aws_fully_configured

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

TEST_LAT = 44.0
TEST_LON = -83.0
TEST_ODOR_INDEX = 10

# Minimal fake D array: 80 direction bins × 3 probability levels (5%, 3%, 1.5%)
FAKE_D = np.ones((80, 3), dtype=float) * 0.5


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mocked_fod3():
    """Patch all fod3 helpers called by build_fod_response with lightweight stubs.

    Allows TestBuildFodResponse to run without real wind data or S3.
    """
    fake_geojson = {"type": "FeatureCollection", "features": []}
    fake_fod_dict = {
        "5percent": [0.5] * 80,
        "3percent": [0.4] * 80,
        "1.5percent": [0.3] * 80,
    }
    with patch("mioffset.mioffset.fod2dict", return_value=fake_fod_dict), \
         patch("mioffset.mioffset.setback_text_table", return_value="table text"), \
         patch("mioffset.mioffset.footprint_plots", return_value=MagicMock()), \
         patch("mioffset.mioffset.matplotlib_to_svg", return_value="<svg></svg>"), \
         patch("mioffset.mioffset.fod_plot_to_ll", return_value=np.zeros((81, 3, 2))), \
         patch("mioffset.mioffset.fod_geojson", return_value=fake_geojson):
        yield


# ---------------------------------------------------------------------------
# TestConfigFromEnv
# ---------------------------------------------------------------------------

class TestConfigFromEnv:
    """config_from_env() should return a dict with the three expected keys."""

    def test_returns_dict(self, monkeypatch):
        monkeypatch.setenv("NARR_BUCKET", "test-bucket")
        monkeypatch.setenv("NARR_DATA_DIR", "test-dir")
        monkeypatch.setenv("NARR_GRID_LATLON_S3", "test-grid.h5")
        from mioffset.mioffset import config_from_env
        assert isinstance(config_from_env(), dict)

    def test_has_required_keys(self, monkeypatch):
        monkeypatch.setenv("NARR_BUCKET", "b")
        monkeypatch.setenv("NARR_DATA_DIR", "d")
        monkeypatch.setenv("NARR_GRID_LATLON_S3", "g")
        from mioffset.mioffset import config_from_env
        result = config_from_env()
        assert {"narr_bucket", "narr_data_dir", "narr_grid_file"} <= result.keys()

    def test_reads_values_from_env(self, monkeypatch):
        monkeypatch.setenv("NARR_BUCKET", "my-bucket")
        monkeypatch.setenv("NARR_DATA_DIR", "my-dir")
        monkeypatch.setenv("NARR_GRID_LATLON_S3", "my-grid.h5")
        from mioffset.mioffset import config_from_env
        result = config_from_env()
        assert result["narr_bucket"] == "my-bucket"
        assert result["narr_data_dir"] == "my-dir"
        assert result["narr_grid_file"] == "my-grid.h5"

    def test_missing_bucket_returns_empty_string(self, monkeypatch):
        # patch load_dotenv to prevent the .env file from repopulating the var
        monkeypatch.delenv("NARR_BUCKET", raising=False)
        with patch("mioffset.mioffset.load_dotenv"):
            from mioffset.mioffset import config_from_env
            assert config_from_env()["narr_bucket"] == ""

    def test_missing_data_dir_returns_empty_string(self, monkeypatch):
        monkeypatch.delenv("NARR_DATA_DIR", raising=False)
        with patch("mioffset.mioffset.load_dotenv"):
            from mioffset.mioffset import config_from_env
            assert config_from_env()["narr_data_dir"] == ""


# ---------------------------------------------------------------------------
# TestBuildFodResponse — fod3 helpers mocked, no S3 needed
# ---------------------------------------------------------------------------

class TestBuildFodResponse:
    """build_fod_response() should return a JSON-serializable dict."""

    def test_returns_dict(self, mocked_fod3):
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        assert isinstance(result, dict)

    def test_has_meta_key(self, mocked_fod3):
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        assert "meta" in result

    def test_has_inputs_key(self, mocked_fod3):
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        assert "inputs" in result

    def test_has_outputs_key(self, mocked_fod3):
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        assert "outputs" in result

    def test_inputs_lat_lon_oef(self, mocked_fod3):
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        assert result["inputs"]["lat"] == TEST_LAT
        assert result["inputs"]["lon"] == TEST_LON
        assert result["inputs"]["oef"] == TEST_ODOR_INDEX

    def test_meta_version(self, mocked_fod3):
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX, version="2.0")
        assert result["meta"]["version"] == "2.0"

    def test_meta_has_timestamp(self, mocked_fod3):
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        assert "timestamp" in result["meta"]

    def test_outputs_has_raw_table_map_plot(self, mocked_fod3):
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        outputs = result["outputs"]
        assert "raw" in outputs
        assert "table" in outputs
        assert "map" in outputs
        assert "plot" in outputs

    def test_response_is_json_serializable(self, mocked_fod3):
        """The complete response dict must round-trip through json.dumps/loads."""
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_json_roundtrip_preserves_inputs(self, mocked_fod3):
        from mioffset.mioffset import build_fod_response
        result = build_fod_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        recovered = json.loads(json.dumps(result))
        assert recovered["inputs"]["lat"] == TEST_LAT
        assert recovered["inputs"]["lon"] == TEST_LON
        assert recovered["inputs"]["oef"] == TEST_ODOR_INDEX


# ---------------------------------------------------------------------------
# Integration tests — require real AWS credentials + NARR_BUCKET
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    not aws_fully_configured(),
    reason="AWS credentials or NARR_BUCKET not configured",
)
class TestFodRunS3:
    """fod_run_s3() with real S3 data."""

    def test_returns_ndarray(self):
        from mioffset.mioffset import fod_run_s3, config_from_env
        from mioffset.aws import get_aws_config, get_s3_client
        cfg = config_from_env()
        s3 = get_s3_client(get_aws_config())
        D = fod_run_s3(TEST_LAT, TEST_LON, TEST_ODOR_INDEX,
                       s3, cfg["narr_bucket"], cfg["narr_data_dir"], cfg["narr_grid_file"])
        assert isinstance(D, np.ndarray)

    def test_result_shape_is_80x3(self):
        from mioffset.mioffset import fod_run_s3, config_from_env
        from mioffset.aws import get_aws_config, get_s3_client
        cfg = config_from_env()
        s3 = get_s3_client(get_aws_config())
        D = fod_run_s3(TEST_LAT, TEST_LON, TEST_ODOR_INDEX,
                       s3, cfg["narr_bucket"], cfg["narr_data_dir"], cfg["narr_grid_file"])
        assert D.shape == (80, 3)


@pytest.mark.integration
@pytest.mark.skipif(
    not aws_fully_configured(),
    reason="AWS credentials or NARR_BUCKET not configured",
)
class TestApiHandler:
    """api_handler() end-to-end."""

    def test_returns_dict(self):
        from mioffset.mioffset import api_handler
        event = {"lat": TEST_LAT, "lon": TEST_LON, "odor_index": TEST_ODOR_INDEX}
        result = api_handler(event, context=None)
        assert isinstance(result, dict)

    def test_response_is_json_serializable(self):
        from mioffset.mioffset import api_handler
        event = {"lat": TEST_LAT, "lon": TEST_LON, "odor_index": TEST_ODOR_INDEX}
        result = api_handler(event, context=None)
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_response_has_meta_inputs_outputs(self):
        from mioffset.mioffset import api_handler
        event = {"lat": TEST_LAT, "lon": TEST_LON, "odor_index": TEST_ODOR_INDEX}
        result = api_handler(event, context=None)
        assert "meta" in result
        assert "inputs" in result
        assert "outputs" in result
