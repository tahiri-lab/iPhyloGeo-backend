"""
Tests for job management endpoints.

POST /api/jobs
GET  /api/jobs/{result_id}/status
"""

import json
from unittest.mock import patch

import pandas as pd
from bson import ObjectId

FAKE_FILE_ID = ObjectId("507f1f77bcf86cd799439011")
FAKE_RESULT_ID = ObjectId("507f1f77bcf86cd799439012")
STR_FILE_ID = str(FAKE_FILE_ID)
STR_RESULT_ID = str(FAKE_RESULT_ID)

# Column-oriented dict matching df.to_json() output format
CLIMATIC_FILE_DATA = {
    "specimen_id": {"0": "sampleA", "1": "sampleB"},
    "temperature": {"0": 25.5, "1": 18.3},
    "rainfall": {"0": 100.0, "1": 250.0},
}

CLIMATIC_DOC = {
    "_id": FAKE_FILE_ID,
    "file_name": "climatic.csv",
    "type": "climatic",
    "file": CLIMATIC_FILE_DATA,
}

BASE_JOB_PAYLOAD = {
    "climatic_file_id": STR_FILE_ID,
    "name": "test_job",
    "lang": "en",
}


# ── POST /api/jobs ─────────────────────────────────────────────────────────────


def test_create_job_returns_result_id(client, files_col, results_col):
    files_col.find_one.return_value = CLIMATIC_DOC
    r = client.post("/api/jobs", json=BASE_JOB_PAYLOAD)
    assert r.status_code == 200
    data = r.json()
    assert "result_id" in data
    assert data["result_id"] == STR_RESULT_ID


def test_create_job_enqueues_pipeline(client, files_col, results_col):
    from utils.background_tasks import task_queue

    files_col.find_one.return_value = CLIMATIC_DOC
    client.post("/api/jobs", json=BASE_JOB_PAYLOAD)
    task_queue.enqueue.assert_called_once()


def test_create_job_climatic_file_not_found_returns_404(client, files_col):
    files_col.find_one.return_value = None
    r = client.post("/api/jobs", json=BASE_JOB_PAYLOAD)
    assert r.status_code == 404


def test_create_job_with_climatic_params(client, files_col, results_col):
    files_col.find_one.return_value = CLIMATIC_DOC
    payload = {**BASE_JOB_PAYLOAD, "climatic_params": {"names": ["temperature"]}}
    r = client.post("/api/jobs", json=payload)
    assert r.status_code == 200


def test_create_temporary_job(client, files_col, results_col):
    files_col.find_one.return_value = CLIMATIC_DOC
    payload = {**BASE_JOB_PAYLOAD, "temporary": True}
    with patch("db.controllers.results.create_temp_result", return_value=STR_RESULT_ID):
        r = client.post("/api/jobs", json=payload)
    assert r.status_code == 200
    assert "result_id" in r.json()


def test_create_job_invalid_climatic_id_returns_500(client, files_col):
    files_col.find_one.side_effect = Exception("invalid ObjectId")
    payload = {**BASE_JOB_PAYLOAD, "climatic_file_id": "bad-id"}
    r = client.post("/api/jobs", json=payload)
    assert r.status_code == 500
    files_col.find_one.side_effect = None


# ── GET /api/jobs/{result_id}/status ──────────────────────────────────────────


def test_get_job_status_not_in_rq_and_not_in_db(client, results_col):
    results_col.find_one.return_value = None
    r = client.get(f"/api/jobs/{STR_RESULT_ID}/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "not_found"
    assert data["progress"] == 0


def test_get_job_status_complete_from_db(client, results_col):
    results_col.find_one.return_value = {
        "_id": FAKE_RESULT_ID,
        "status": "complete",
    }
    r = client.get(f"/api/jobs/{STR_RESULT_ID}/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "complete"
    assert data["progress"] == 100


def test_get_job_status_error_from_db(client, results_col):
    results_col.find_one.return_value = {
        "_id": FAKE_RESULT_ID,
        "status": "error",
    }
    r = client.get(f"/api/jobs/{STR_RESULT_ID}/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "error"
    assert data["progress"] == 0


def test_get_job_status_pending_from_db(client, results_col):
    results_col.find_one.return_value = {
        "_id": FAKE_RESULT_ID,
        "status": "pending",
    }
    r = client.get(f"/api/jobs/{STR_RESULT_ID}/status")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
