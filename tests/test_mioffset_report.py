"""
tests/test_mioffset_report.py

Tests for functions in mioffset/mioffset_report.py.

This file covers the reporting/export path that is separate from the web API
response helpers in mioffset.py.

Test structure
--------------
Pure unit tests (always run, no external resources needed):
  - TestBuildReportResponse — build_report_response() returns JSON-serializable dict

Integration tests (@pytest.mark.integration):
  Skipped automatically when AWS credentials, NARR_BUCKET, or NARR_GRID_LATLON_S3 are absent.
  - TestFodS3ReportFlow — fod() pulls wind JSON from S3 and reaches report writers

Run only fast tests:
    pytest -m "not integration"

Run all tests (including live S3):
    pytest
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from conftest import aws_fully_configured
from mioffset.aws import get_s3_client
from mioffset.narr_data import wind_data_factory


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

TEST_LAT = 44.0
TEST_LON = -83.0
TEST_ODOR_INDEX = 10
TEST_DATA_DIR = str(Path(__file__).parent / "data")

# Minimal fake D array: 80 direction bins × 3 probability levels (5%, 3%, 1.5%)
FAKE_D = np.ones((80, 3), dtype=float) * 0.5


def _mock_report_helpers():
    fake_geojson = {"type": "FeatureCollection", "features": []}
    fake_fod_dict = {
        "5percent": [0.5] * 80,
        "3percent": [0.4] * 80,
        "1.5percent": [0.3] * 80,
    }
    return patch("mioffset.mioffset_report.fod2dict", return_value=fake_fod_dict), \
        patch("mioffset.mioffset_report.setback_text_table", return_value="table text"), \
        patch("mioffset.mioffset_report.footprint_plots"), \
        patch("mioffset.mioffset_report.matplotlib_to_svg", return_value="<svg></svg>"), \
        patch("mioffset.mioffset_report.fod_plot_to_ll", return_value=np.zeros((81, 3, 2))), \
        patch("mioffset.mioffset_report.fod_geojson", return_value=fake_geojson)


# ---------------------------------------------------------------------------
# TestBuildReportResponse
# ---------------------------------------------------------------------------


class TestBuildReportResponse:
    """build_report_response() should return a JSON-serializable dict."""

    @pytest.fixture
    def mocked_report_helpers(self):
        fake_geojson = {"type": "FeatureCollection", "features": []}
        fake_fod_dict = {
            "5percent": [0.5] * 80,
            "3percent": [0.4] * 80,
            "1.5percent": [0.3] * 80,
        }
        with patch("mioffset.mioffset_report.fod2dict", return_value=fake_fod_dict), \
             patch("mioffset.mioffset_report.setback_text_table", return_value="table text"), \
             patch("mioffset.mioffset_report.footprint_plots"), \
             patch("mioffset.mioffset_report.matplotlib_to_svg", return_value="<svg></svg>"), \
             patch("mioffset.mioffset_report.fod_plot_to_ll", return_value=np.zeros((81, 3, 2))), \
             patch("mioffset.mioffset_report.fod_geojson", return_value=fake_geojson):
            yield

    def test_returns_dict(self, mocked_report_helpers):
        from mioffset.mioffset_report import build_report_response
        result = build_report_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        assert isinstance(result, dict)

    def test_has_meta_inputs_outputs(self, mocked_report_helpers):
        from mioffset.mioffset_report import build_report_response
        result = build_report_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        assert "meta" in result
        assert "inputs" in result
        assert "outputs" in result

    def test_outputs_include_table_map_plot(self, mocked_report_helpers):
        from mioffset.mioffset_report import build_report_response
        result = build_report_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        outputs = result["outputs"]
        assert "raw" in outputs
        assert "table" in outputs
        assert "map" in outputs
        assert "plot" in outputs

    def test_response_is_json_serializable(self, mocked_report_helpers):
        from mioffset.mioffset_report import build_report_response
        result = build_report_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_json_roundtrip_preserves_inputs(self, mocked_report_helpers):
        from mioffset.mioffset_report import build_report_response
        result = build_report_response(FAKE_D, TEST_LAT, TEST_LON, TEST_ODOR_INDEX)
        recovered = json.loads(json.dumps(result))
        assert recovered["inputs"]["lat"] == TEST_LAT
        assert recovered["inputs"]["lon"] == TEST_LON
        assert recovered["inputs"]["oef"] == TEST_ODOR_INDEX


# ---------------------------------------------------------------------------
# Integration tests — require real AWS credentials + S3 configuration
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.s3
@pytest.mark.skipif(
    not aws_fully_configured(),
    reason="AWS credentials or NARR_BUCKET not configured",
)
class TestFodS3ReportFlow:
    """fod() with real S3 wind data, with filesystem writers mocked out."""

    @pytest.fixture(scope="class")
    def s3_grid_key(self):
        key = os.getenv("NARR_GRID_LATLON_S3", "")
        if not key:
            pytest.skip("NARR_GRID_LATLON_S3 is required for report integration tests")
        return key

    @pytest.fixture(scope="class")
    def wind_data_real_s3(self, s3_grid_key):
        bucket = os.getenv("NARR_BUCKET", "")
        s3_client = get_s3_client()
        return wind_data_factory(
            location="S3",
            narr_grid_file=s3_grid_key,
            narr_data_dir=TEST_DATA_DIR,
            narr_bucket=bucket,
            s3_client=s3_client,
        )

    def test_fod_reads_s3_json_and_reaches_report_writers(self, wind_data_real_s3, tmp_path):
        from mioffset.mioffset_report import fod

        def keep_small_windows(ts, tstart=0, tend=2920):
            return {key: value[:25] for key, value in ts.items()}

        with patch("mioffset.mioffset_report.filter_narr_timeseries", side_effect=keep_small_windows), \
             patch("mioffset.mioffset_report.write_footprint_plots", return_value=("plot1.png", "plot2.png")) as mock_write_plots, \
             patch("mioffset.mioffset_report.write_pointsource_shapefile", return_value=["point.dbf", "point.shp", "point.shx"]) as mock_point, \
             patch("mioffset.mioffset_report.write_footprint_shapefile", return_value=["foot.dbf", "foot.shp", "foot.shx"]) as mock_foot, \
             patch("mioffset.mioffset_report.write_zipfile", return_value="bundle.zip") as mock_zip, \
             patch("mioffset.mioffset_report.write_kml") as mock_kml:
            result = fod(
                TEST_LAT,
                TEST_LON,
                TEST_ODOR_INDEX,
                file_prefix="",
                time_flag="F",
                output_offset_dir=str(tmp_path),
                wind_data=wind_data_real_s3,
            )

        assert result is None
        assert mock_write_plots.called
        assert mock_point.called
        assert mock_foot.called
        assert mock_zip.called
        assert mock_kml.called
