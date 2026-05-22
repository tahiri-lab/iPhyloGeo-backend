"""
Global test configuration.

All external-service mocks (pymongo, redis, rq) are applied at module level,
BEFORE any backend module is imported, so that module-level initialisation in
db/db_validator.py, utils/background_tasks.py, etc. uses mocked objects.
"""

import os
import sys
from unittest.mock import MagicMock
import redis_client
import redis

from bson import ObjectId

# ── Environment variables ──────────────────────────────────────────────────────
os.environ["MONGO_URI"] = "mongodb://localhost:27017"
os.environ["DB_NAME"] = "test_db"
os.environ["REDIS_URL"] = "redis://localhost:6379"

# ── Fake exception classes ─────────────────────────────────────────────────────
class _FakeRedisError(Exception):
    pass


class _FakeNoSuchJobError(Exception):
    pass


# ── Mock redis ─────────────────────────────────────────────────────────────────
_mock_redis_conn = MagicMock()
_mock_redis_conn.get.return_value = None
_mock_redis_conn.ping.return_value = True

redis_client._r = _mock_redis_conn

# ── Mock rq ───────────────────────────────────────────────────────────────────
_mock_rq_job_instance = MagicMock()
_mock_rq_job_instance.meta = {}

_mock_rq_queue = MagicMock()
_mock_rq_queue.enqueue.return_value = _mock_rq_job_instance

_mock_rq_exceptions = MagicMock()
_mock_rq_exceptions.NoSuchJobError = _FakeNoSuchJobError

_mock_rq_job_class = MagicMock()
_mock_rq_job_class.fetch.side_effect = _FakeNoSuchJobError("not found")

_mock_rq_module = MagicMock()
_mock_rq_module.Queue.return_value = _mock_rq_queue
_mock_rq_module.get_current_job.return_value = None

_mock_rq_job_module = MagicMock()
_mock_rq_job_module.Job = _mock_rq_job_class

sys.modules["rq"] = _mock_rq_module
sys.modules["rq.exceptions"] = _mock_rq_exceptions
sys.modules["rq.job"] = _mock_rq_job_module

# ── Mock pymongo ───────────────────────────────────────────────────────────────
FAKE_FILE_ID = ObjectId("507f1f77bcf86cd799439011")
FAKE_RESULT_ID = ObjectId("507f1f77bcf86cd799439012")

_mock_files_col = MagicMock()
_mock_results_col = MagicMock()

_mock_mongo_db = MagicMock()
_mock_mongo_db.list_collection_names.return_value = ["Files", "Results"]
_mock_mongo_db.command.return_value = {}
_mock_mongo_db.Files = _mock_files_col
_mock_mongo_db.Results = _mock_results_col
_mock_mongo_db.__getitem__.side_effect = (
    lambda n: _mock_files_col if n == "Files" else _mock_results_col
)

_mock_mongo_client = MagicMock()
_mock_mongo_client.get_database.return_value = _mock_mongo_db
_mock_mongo_client.__getitem__.return_value = _mock_mongo_db

_mock_pymongo = MagicMock()
_mock_pymongo.MongoClient.return_value = _mock_mongo_client

sys.modules["pymongo"] = _mock_pymongo

# ── Backend imports (safe after all mocks are in place) ────────────────────────
import pytest
from fastapi.testclient import TestClient
from main import app


# ── Fixtures ───────────────────────────────────────────────────────────────────
@pytest.fixture
def test_redis():
    r = redis.Redis.from_url("redis://localhost:6380", decode_responses=True)
    r.flushdb()
    yield r
    r.flushdb()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def files_col():
    """Exposes the files MongoDB mock collection for per-test configuration."""
    return _mock_files_col


@pytest.fixture
def results_col():
    """Exposes the results MongoDB mock collection for per-test configuration."""
    return _mock_results_col


@pytest.fixture(autouse=True)
def reset_mocks():
    """Restore predictable mock state before every test."""
    _mock_files_col.reset_mock()
    _mock_results_col.reset_mock()
    _mock_rq_queue.reset_mock()
    _mock_rq_job_instance.meta = {}
    _mock_rq_queue.enqueue.return_value = _mock_rq_job_instance

    # Default insert responses
    _mock_files_col.insert_one.return_value.inserted_id = FAKE_FILE_ID
    _mock_results_col.insert_one.return_value.inserted_id = FAKE_RESULT_ID

    # Default query responses (nothing found)
    _mock_files_col.find.return_value = iter([])
    _mock_results_col.find.return_value = iter([])
    _mock_files_col.find_one.return_value = None
    _mock_results_col.find_one.return_value = None

    yield
