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


def run_sweeper():
    try:
        asyncio.run(start_mongodb_sweeper())
    except InterruptedError:
        pass


def mock_alive_worker(mock_fetch, mock_workers):
    """
    Creates a Redis started job with a matching active worker.
    """
    mock_job = MagicMock()
    mock_job.get_status.return_value = "started"
    mock_job.worker_name = "worker-1"

    mock_fetch.return_value = mock_job

    worker = MagicMock()
    worker.name = "worker-1"

    mock_workers.return_value = [worker]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Missing Redis job → mark error
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_marks_error_when_job_missing_from_redis(results_col):
    stale_time = datetime.now(timezone.utc) - (STALE_THRESHOLD + timedelta(minutes=1))

    results_col.find.return_value = [
        {
            "_id": STALE_RESULT_ID,
            "status": "running",
            "created_at": stale_time,
        }
    ]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_fetch.side_effect = NoSuchJobError()

        run_sweeper()

    results_col.update_one.assert_called_once_with(
        {"_id": STALE_RESULT_ID},
        {"$set": {"status": "error"}},
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Active Redis job → no DB mutation
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_stands_down_on_active_redis_jobs(results_col):
    created_at = datetime.now(timezone.utc) - (
        SUSPICIOUS_THRESHOLD - timedelta(minutes=1)
    )

    results_col.find.return_value = [
        {
            "_id": STALE_RESULT_ID,
            "status": "alignment",
            "created_at": created_at,
        }
    ]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.Worker.all") as mock_workers,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_alive_worker(mock_fetch, mock_workers)

        run_sweeper()

    results_col.update_one.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Stale threshold → force error
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_marks_error_when_job_exceeds_stale_threshold(results_col):
    stale_time = datetime.now(timezone.utc) - (STALE_THRESHOLD + timedelta(minutes=1))

    results_col.find.return_value = [
        {
            "_id": STALE_RESULT_ID,
            "status": "running",
            "created_at": stale_time,
        }
    ]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.Worker.all") as mock_workers,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_alive_worker(mock_fetch, mock_workers)

        run_sweeper()

    args, _ = results_col.update_one.call_args

    assert args[0]["_id"] == STALE_RESULT_ID
    assert args[1]["$set"]["status"] == "error"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Suspicious threshold → mark UI flag only
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_marks_job_as_taking_very_long(results_col):
    created_at = datetime.now(timezone.utc) - timedelta(hours=2)

    results_col.find.return_value = [
        {
            "_id": STALE_RESULT_ID,
            "status": "running",
            "created_at": created_at,
        }
    ]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.Worker.all") as mock_workers,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_job = MagicMock()
        mock_job.get_status.return_value = "started"
        mock_job.worker_name = "worker-1"

        mock_fetch.return_value = mock_job

        worker = MagicMock()
        worker.name = "worker-1"

        mock_workers.return_value = [worker]

        run_sweeper()

    results_col.update_one.assert_called_once_with(
        {
            "_id": STALE_RESULT_ID,
            "is_taking_very_long": {"$ne": True},
        },
        {
            "$set": {
                "is_taking_very_long": True,
            }
        },
    )

# ─────────────────────────────────────────────────────────────────────────────
# 5. Redis error → fail safe, no DB mutation
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_does_not_modify_db_on_redis_error(results_col):
    created_at = datetime.now(timezone.utc) - (STALE_THRESHOLD + timedelta(hours=1))

    results_col.find.return_value = [
        {
            "_id": STALE_RESULT_ID,
            "status": "running",
            "created_at": created_at,
        }
    ]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        mock_fetch.side_effect = ConnectionError("Redis down")

        run_sweeper()

    results_col.update_one.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Started Redis job but worker missing → mark error
# ─────────────────────────────────────────────────────────────────────────────
def test_sweeper_marks_error_when_worker_disappears(results_col):
    created_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    results_col.find.return_value = [
        {
            "_id": STALE_RESULT_ID,
            "status": "running",
            "created_at": created_at,
        }
    ]

    with (
        patch("utils.sweeper.results_db", results_col),
        patch("utils.sweeper.redis_connection", MagicMock()),
        patch("utils.sweeper.Job.fetch") as mock_fetch,
        patch("utils.sweeper.Worker.all") as mock_workers,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError),
    ):
        job = MagicMock()
        job.get_status.return_value = "started"
        job.worker_name = "dead-worker"

        mock_fetch.return_value = job

        worker = MagicMock()
        worker.name = "different-worker"

        mock_workers.return_value = [worker]

        run_sweeper()

    results_col.update_one.assert_called_once_with(
        {"_id": STALE_RESULT_ID},
        {"$set": {"status": "error"}},
    )
