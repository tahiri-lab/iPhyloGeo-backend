from unittest.mock import MagicMock, patch
from bson import ObjectId
from datetime import datetime, timedelta, timezone
from rq.exceptions import NoSuchJobError
import asyncio

from utils.sweeper import (
    start_mongodb_sweeper,
    SUSPICIOUS_THRESHOLD,
    STALE_THRESHOLD,
)

STALE_RESULT_ID = ObjectId("607f1f77bcf86cd79943900a")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Missing Redis job → mark error
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_marks_error_when_job_missing_from_redis(results_col):
    """
    Scenario: Job exceeds stale threshold and is missing in Redis.
    Expectation: Sweeper marks it as error.
    """

    stale_time = datetime.now(timezone.utc) - (STALE_THRESHOLD + timedelta(minutes=1))

    doc = {
        "_id": STALE_RESULT_ID,
        "status": "running",
        "created_at": stale_time,
    }

    results_col.find.return_value = [doc]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_fetch.side_effect = NoSuchJobError()

        try:
            asyncio.run(start_mongodb_sweeper())
        except InterruptedError:
            pass

    results_col.update_one.assert_called_once_with(
        {"_id": STALE_RESULT_ID},
        {"$set": {"status": "error"}},
    )

# ─────────────────────────────────────────────────────────────────────────────
# 2. Active Redis job → no DB mutation
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_stands_down_on_active_redis_jobs(results_col):
    """
    Scenario: Job exists in Redis and is still running.
    Expectation: Sweeper does nothing.
    """

    stale_time = datetime.now(timezone.utc) - (
        SUSPICIOUS_THRESHOLD - timedelta(minutes=1)
    )

    doc = {
        "_id": STALE_RESULT_ID,
        "status": "alignment",
        "created_at": stale_time,
    }

    results_col.find.return_value = [doc]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_job = MagicMock()
        mock_job.get_status.return_value = "started"
        mock_fetch.return_value = mock_job

        try:
            asyncio.run(start_mongodb_sweeper())
        except InterruptedError:
            pass

    results_col.update_one.assert_not_called()

# ─────────────────────────────────────────────────────────────────────────────
# 3. Stale threshold → force error
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_marks_error_when_job_exceeds_stale_threshold(results_col):
    """
    Scenario: Job exceeds stale threshold.
    Expectation: Sweeper marks error.
    """

    stale_time = datetime.now(timezone.utc) - (STALE_THRESHOLD + timedelta(minutes=1))

    doc = {
        "_id": STALE_RESULT_ID,
        "status": "running",
        "created_at": stale_time,
    }

    results_col.find.return_value = [doc]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_job = MagicMock()
        mock_job.get_status.return_value = "started"
        mock_fetch.return_value = mock_job

        try:
            asyncio.run(start_mongodb_sweeper())
        except InterruptedError:
            pass

    results_col.update_one.assert_called_once()
    args, _ = results_col.update_one.call_args

    assert args[0]["_id"] == STALE_RESULT_ID
    assert args[1]["$set"]["status"] == "error"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Suspicious threshold → mark UI flag only
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_marks_job_as_taking_very_long(results_col):
    """
    Scenario: Job exceeds suspicious threshold but not stale threshold.
    Expectation: Sweeper sets is_taking_very_long = True.
    """

    created_at = datetime.now(timezone.utc) - (
        SUSPICIOUS_THRESHOLD + timedelta(minutes=1)
    )

    doc = {
        "_id": STALE_RESULT_ID,
        "status": "running",
        "created_at": created_at,
    }

    results_col.find.return_value = [doc]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_job = MagicMock()
        mock_job.get_status.return_value = "started"
        mock_fetch.return_value = mock_job

        try:
            asyncio.run(start_mongodb_sweeper())
        except InterruptedError:
            pass

    results_col.update_one.assert_called_once_with(
        {"_id": STALE_RESULT_ID},
        {"$set": {"is_taking_very_long": True}},
    )

# ─────────────────────────────────────────────────────────────────────────────
# 5. Redis error → fail safe, no DB mutation
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_does_not_modify_db_on_redis_error(results_col):
    """
    Scenario: Redis throws unexpected error during fetch.
    Expectation: Sweeper does not touch MongoDB.
    """

    created_at = datetime.now(timezone.utc) - (STALE_THRESHOLD + timedelta(hours=1))

    doc = {
        "_id": STALE_RESULT_ID,
        "status": "running",
        "created_at": created_at,
    }

    results_col.find.return_value = [doc]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_fetch.side_effect = ConnectionError("Redis down")

        try:
            asyncio.run(start_mongodb_sweeper())
        except InterruptedError:
            pass

    results_col.update_one.assert_not_called()
