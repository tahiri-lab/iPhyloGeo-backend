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

class FakeCursor:
    def __init__(self, items):
        self.items = list(items)
    def sort(self, field, direction):
        self.items.sort(
            key=lambda x: x.get(field),
            reverse=direction == -1,
        )
        return self
    def skip(self, n):
        self.items = self.items[n:]
        return self
    def limit(self, n):
        self.items = self.items[:n]
        return self
    def __iter__(self):
        return iter(self.items)

def _make_result_doc(status="complete", with_output=True):
    doc = {
        "_id": FAKE_RESULT_ID,
        "name": "test_result",
        "created_at": 1,
        "status": status,
        "result_type": ["climatic", "genetic"],
    }
    if with_output:
        doc["output"] = {"Gene": ["geneA", "geneB"], "Bootstrap": [90, 85]}
    return doc

def _make_other_result_doc(created_at=2):
    doc = _make_result_doc()
    doc["_id"] = ObjectId("507f1f77bcf86cd799439099")
    doc["name"] = "second"
    doc["created_at"] = created_at
    return doc

# ── List results ───────────────────────────────────────────────────────────────


def test_list_results_empty(client, results_col):
    results_col.find.return_value = FakeCursor([])
    results_col.count_documents.return_value = 0
    r = client.get("/api/results?limit=49&skip=0")
    assert r.status_code == 200
    assert r.json() == {
        "data": [],
        "total": 0,
        "skip": 0,
        "limit": 49,
    }


def test_list_results_returns_serialised_docs(client, results_col):
    results_col.find.return_value = FakeCursor([_make_result_doc()])
    results_col.count_documents.return_value = 1
    r = client.get("/api/results?limit=30&skip=0")
    assert r.status_code == 200
    results = r.json()
    data = results["data"]
    assert results["total"] == 1
    assert results["skip"] == 0
    assert results["limit"] == 30
    assert len(data) == 1
    assert isinstance(data[0]["_id"], str)
    assert data[0]["name"] == "test_result"


def test_list_results_multiple_docs(client, results_col):
    results_col.find.return_value = FakeCursor([_make_result_doc(), _make_other_result_doc()])
    results_col.count_documents.return_value = 2
    r = client.get("/api/results?limit=45&skip=0")
    results = r.json()
    data = results["data"]
    assert results["total"] == 2
    assert results["skip"] == 0
    assert results["limit"] == 45
    assert r.status_code == 200
    assert len(data) == 2

def test_list_results_multiple_docs_skip(client, results_col):
    results_col.find.return_value = FakeCursor([_make_result_doc(), _make_other_result_doc()])
    results_col.count_documents.return_value = 2
    r = client.get("/api/results?limit=45&skip=1")
    results = r.json()
    data = results["data"]
    assert results["total"] == 1
    assert results["skip"] == 1
    assert results["limit"] == 45
    assert r.status_code == 200
    assert len(data) == 1

def test_list_results_multiple_docs_limit(client, results_col):
    results_col.find.return_value = FakeCursor([_make_result_doc(), _make_other_result_doc()])
    results_col.count_documents.return_value = 2
    r = client.get("/api/results?limit=1&skip=0")
    results = r.json()
    data = results["data"]
    assert results["total"] == 1
    assert results["skip"] == 0
    assert results["limit"] == 1
    assert r.status_code == 200
    assert len(data) == 1


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
def _post_email_request(client, email_address, returns: bool):
    with patch("api.routes.results.mail.send_results_ready_email", return_value=returns):
        return client.post(
            f"/api/results/{STR_ID}/email",
            json={"email": email_address, "lang": "en"},
        )

def test_email_result_success(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    r = _post_email_request(client, "willbou2@gmail.com", True)
    assert r.status_code == 202
    assert "queued" in r.json()["message"].lower()

def test_email_result_rate_limit_returns_429(client, results_col, test_redis):
    
    # Most of the time, we do not care about testing Redis, but here, we absolutely need to
    with patch("redis_client.get_redis", return_value=test_redis):
        # We want this API endpoint to block when there are 10 requests in a minute
        results_col.find_one.return_value = _make_result_doc()
        for _ in range(10):
            r = _post_email_request(client, "willbou2@gmail.com", True)
            assert r.status_code == 202

        for _ in range(2):
            r = _post_email_request(client, "willbou2@gmail.com", True)
            assert r.status_code == 429
            assert "banned" in r.json()["detail"].lower()

        # We get rid of the ban by resetting redis
        test_redis.flushdb()
        for _ in range(10):
            r = _post_email_request(client, "willbou2@gmail.com", True)
            assert r.status_code == 202

def test_email_result_bad_formatting_returns_400(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    r = _post_email_request(client, "testexample.com", True)
    assert r.status_code == 400
    message = r.json()["detail"].lower()
    assert "invalid" in message and "format" in message

def test_email_result_invalid_domain_returns_400(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    r = _post_email_request(client, "test@example.com", True)
    assert r.status_code == 400
    message = r.json()["detail"].lower()
    assert "invalid" in message and "domain" in message


def test_email_result_url_format(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    with patch("api.routes.results.mail.send_results_ready_email", return_value=True) as mock_send:
        r = client.post(
            f"/api/results/{STR_ID}/email",
            json={"email": "willbou2@gmail.com", "lang": "en"},
        )
    assert r.status_code == 202
    mock_send.assert_called_once_with("willbou2@gmail.com", f"/results?id={STR_ID}", "en")

def test_email_result_invalid_lang_returns_422(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    with patch("api.routes.results.mail.send_results_ready_email", return_value=True):
        r = client.post(
            f"/api/results/{STR_ID}/email",
            json={"email": "willbou2@gmail.com", "lang": "de"},
        )
    assert r.status_code == 422

def test_email_result_spanish_success(client, results_col):
    results_col.find_one.return_value = _make_result_doc()
    with patch("api.routes.results.mail.send_results_ready_email", return_value=True) as mock_send:
        r = client.post(
            f"/api/results/{STR_ID}/email",
            json={"email": "willbou2@gmail.com", "lang": "es"},
        )
    assert r.status_code == 202
    mock_send.assert_called_once_with("willbou2@gmail.com", f"/results?id={STR_ID}", "es")
