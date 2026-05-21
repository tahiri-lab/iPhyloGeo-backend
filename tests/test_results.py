"""
Tests for the results CRUD endpoints.

GET    /api/results
GET    /api/results/{id}
DELETE /api/results/{id}
GET    /api/results/{id}/download
POST   /api/results/{id}/email
"""

import io
from unittest.mock import patch

import pandas as pd
from bson import ObjectId
import redis

FAKE_RESULT_ID = ObjectId("507f1f77bcf86cd799439012")
STR_ID = str(FAKE_RESULT_ID)


def _make_result_doc(status="complete", with_output=True):
    doc = {
        "_id": FAKE_RESULT_ID,
        "name": "test_result",
        "status": status,
        "result_type": ["climatic", "genetic"],
    }
    if with_output:
        doc["output"] = {"Gene": ["geneA", "geneB"], "Bootstrap": [90, 85]}
    return doc


# ── List results ───────────────────────────────────────────────────────────────


def test_list_results_empty(client, results_col):
    results_col.find.return_value = iter([])
    r = client.get("/api/results")
    assert r.status_code == 200
    assert r.json() == []


def test_list_results_returns_serialised_docs(client, results_col):
    results_col.find.return_value = iter([_make_result_doc()])
    r = client.get("/api/results")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert isinstance(results[0]["_id"], str)
    assert results[0]["name"] == "test_result"


def test_list_results_multiple_docs(client, results_col):
    doc2 = _make_result_doc()
    doc2["_id"] = ObjectId("507f1f77bcf86cd799439099")
    doc2["name"] = "second"
    results_col.find.return_value = iter([_make_result_doc(), doc2])
    r = client.get("/api/results")
    assert r.status_code == 200
    assert len(r.json()) == 2


# ── Get single result ──────────────────────────────────────────────────────────


def test_get_result_found(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    r = client.get(f"/api/results/{STR_ID}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "complete"
    assert isinstance(data["_id"], str)


def test_get_result_not_found_returns_404(client, results_col):
    results_col.find_one.return_value = None
    r = client.get(f"/api/results/{STR_ID}")
    assert r.status_code == 404


# ── Delete result ──────────────────────────────────────────────────────────────


def test_delete_result_returns_204(client, results_col):
    r = client.delete(f"/api/results/{STR_ID}")
    assert r.status_code == 204
    results_col.delete_one.assert_called_once()


# ── Download result ────────────────────────────────────────────────────────────


def test_download_result_no_output_returns_404(client, results_col):
    results_col.find_one.return_value = _make_result_doc(with_output=False)
    r = client.get(f"/api/results/{STR_ID}/download")
    assert r.status_code == 404


def test_download_result_not_found_returns_404(client, results_col):
    results_col.find_one.return_value = None
    r = client.get(f"/api/results/{STR_ID}/download")
    assert r.status_code == 404


def test_download_result_returns_excel(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    r = client.get(f"/api/results/{STR_ID}/download")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert "test_result.xlsx" in r.headers["content-disposition"]
    df = pd.read_excel(io.BytesIO(r.content))
    assert list(df.columns) == ["Gene", "Bootstrap"]
    assert len(df) == 2


# ── Email result ───────────────────────────────────────────────────────────────


def test_email_result_success(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    with patch("api.routes.results.mail.send_results_ready_email", return_value=True):
        r = client.post(
            f"/api/results/{STR_ID}/email",
            json={"email": "willbou2@gmail.com", "lang": "en"},
        )
    assert r.status_code == 200
    assert "sent" in r.json()["message"].lower()

def test_email_result_rate_limit_returns_429(client, results_col, test_redis):
    # Most of the time, we do not care about testing Redis, but here, we absolutely need to
    with patch("redis_client.get_redis", return_value=test_redis):
        # We want this API endpoint to block when there are 10 requests in a minute
        results_col.find_one.return_value = _make_result_doc()
        for _ in range(10):
            with patch("api.routes.results.mail.send_results_ready_email", return_value=True):
                r = client.post(
                    f"/api/results/{STR_ID}/email",
                    json={"email": "willbou2@gmail.com", "lang": "en"},
                )
            assert r.status_code == 200

        for _ in range(2):
            with patch("api.routes.results.mail.send_results_ready_email", return_value=True):
                r = client.post(
                    f"/api/results/{STR_ID}/email",
                    json={"email": "willbou2@gmail.com", "lang": "en"},
                )
            assert r.status_code == 429
            assert "banned" in r.json()["detail"].lower()

def test_email_result_bad_formatting_returns_400(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    with patch("api.routes.results.mail.send_results_ready_email", return_value=True):
        r = client.post(
            f"/api/results/{STR_ID}/email",
            json={"email": "testexample.com", "lang": "en"},
        )
    assert r.status_code == 400
    message = r.json()["detail"].lower()
    assert "invalid" in message and "format" in message

def test_email_result_invalid_domain_returns_400(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    with patch("api.routes.results.mail.send_results_ready_email", return_value=True):
        r = client.post(
            f"/api/results/{STR_ID}/email",
            json={"email": "test@example.com", "lang": "en"},
        )
    assert r.status_code == 400
    message = r.json()["detail"].lower()
    assert "invalid" in message and "domain" in message

def test_email_result_send_failure_returns_500(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    with patch("api.routes.results.mail.send_results_ready_email", return_value=False):
        r = client.post(
            f"/api/results/{STR_ID}/email",
            json={"email": "willbou2@gmail.com", "lang": "en"},
        )
    assert r.status_code == 500
