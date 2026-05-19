"""
Tests for the settings endpoints.

GET /api/settings
PUT /api/settings
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

BASE_SETTINGS = {
    "alignment_method": "PairwiseAlign",
    "distance_method": "LeastSquare",
    "window_size": 100,
    "step_size": 10,
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


def test_update_settings_with_new_key(client, settings_file):
    new_settings = {**BASE_SETTINGS, "extra_param": "value"}
    r = client.put("/api/settings", json=new_settings)
    assert r.status_code == 200
    assert r.json()["extra_param"] == "value"
