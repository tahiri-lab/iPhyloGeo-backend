"""
Tests for the settings endpoints.

GET /api/settings
PUT /api/settings
"""

import json
from unittest.mock import patch

import pytest

from enums import (
    AlignmentMethod,
    DistanceMethod,
    FitMethod,
    MantelTestMethod,
    PreprocessingToggle,
    SimilarityMethod,
    StatisticalTest,
    TreeType,
)

BASE_SETTINGS = {
    "bootstrap_threshold": 100,
    "dist_threshold": 5,
    "window_size": 100,
    "step_size": 1,
    "alignment_method": AlignmentMethod.PAIRWISE_ALIGN,
    "distance_method": DistanceMethod.ALL,
    "fit_method": FitMethod.WIDER_FIT,
    "tree_type": TreeType.BIOPYTHON,
    "rate_similarity": 50,
    "method_similarity": SimilarityMethod.HAMMING,
    "preprocessing_genetic": PreprocessingToggle.DISABLED,
    "preprocessing_climatic": PreprocessingToggle.DISABLED,
    "preprocessing_threshold_genetic": 0.5,
    "preprocessing_threshold_climatic": 0.5,
    "correlation_climatic_enabled": PreprocessingToggle.DISABLED,
    "correlation_threshold_climatic": 0.5,
    "permutations_mantel_test": 999,
    "permutations_protest": 999,
    "mantel_test_method": MantelTestMethod.PEARSON,
    "statistical_test": StatisticalTest.NONE,
}


@pytest.fixture
def settings_file(tmp_path):
    """Create a temporary settings file and patch the module path to it."""
    f = tmp_path / "genetic_settings_file.json"
    f.write_text(json.dumps(BASE_SETTINGS), encoding="utf-8")
    with patch("api.routes.settings._SETTINGS_FILE", f):
        yield f


# ── GET /api/settings ──────────────────────────────────────────────────────────


def test_get_settings_returns_json(client, settings_file):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["alignment_method"] == "PairwiseAlign"
    assert data["window_size"] == 100


def test_get_settings_file_not_found_returns_404(client, tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with patch("api.routes.settings._SETTINGS_FILE", missing):
        r = client.get("/api/settings")
    assert r.status_code == 404


# ── PUT /api/settings ──────────────────────────────────────────────────────────


def test_update_settings_returns_updated_values(client, settings_file):
    new_settings = {**BASE_SETTINGS, "window_size": 200, "step_size": 20}
    r = client.put("/api/settings", json=new_settings)
    assert r.status_code == 200
    assert r.json()["window_size"] == 200


def test_update_settings_persists_to_file(client, settings_file):
    new_settings = {**BASE_SETTINGS, "alignment_method": "MUSCLE"}
    client.put("/api/settings", json=new_settings)
    saved = json.loads(settings_file.read_text(encoding="utf-8"))
    assert saved["alignment_method"] == "MUSCLE"


# Since we have a model for our settings, additional keys should be ignored
def test_update_settings_with_new_key(client, settings_file):
    new_settings = {**BASE_SETTINGS, "extra_param": "value"}
    r = client.put("/api/settings", json=new_settings)
    assert r.status_code == 200
    assert not hasattr(r.json(), "extra_param")


