from unittest.mock import MagicMock, patch
from bson import ObjectId
from datetime import datetime, timedelta, timezone

# Using your exact naming convention and function path
from utils.sweeper import start_mongodb_sweeper

STALE_RESULT_ID = ObjectId("607f1f77bcf86cd79943900a")

# ── Sweeper Background Loop ──────────────────────────────────────────────────
def test_sweeper_cleans_up_stale_job_not_in_redis(results_col):
    """
    Scenario: MongoDB shows a job is 'running' and it's older than 2.5 hours.
    Redis returns None (the job fell out of RAM or worker died completely).
    Expectation: Sweeper updates status to 'error' and wipes fields.
    """
    results_col.database.results = results_col
    
    # Arrange: Force your results_col fixture to return an old orphaned job document
    stale_time = datetime.now(timezone.utc) - timedelta(hours=3)
    orphaned_doc = {
        "_id": STALE_RESULT_ID,
        "status": "running",
        "created_at": stale_time,
        "msaSet": "raw_fasta_alignment_data",
    }
    results_col.find.return_value = [orphaned_doc]
    mock_redis_conn = MagicMock()

    # Act: Run the sweeper, patching asyncio.sleep to break the loop instantly
    with (
        patch("utils.sweeper.Queue") as mock_queue_cls,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError("Stop Loop")),
    ):
        # Redis confirms the job is an absolute ghost (None)
        mock_queue_cls.return_value.fetch_job.return_value = None

        try:
            # We use a dummy wrapper loop to resolve the async coroutine since your suite is sync
            import asyncio

            asyncio.run(start_mongodb_sweeper(results_col.database, mock_redis_conn))
        except InterruptedError:
            pass  # Caught loop-breaker safely

    # Assert: Verify the exact $set schema cleanup update ran against your fixture
    results_col.update_one.assert_called_once_with(
        {"_id": STALE_RESULT_ID},
        {
            "$set": {
                "status": "error",
                "error_message": "Job automatically terminated: Execution exceeded maximum execution time or worker disconnected unexpectedly.",
                "msaSet": None,
                "genetic_trees": None,
                "climatic_trees": None,
                "output": None,
            }
        },
    )

def test_sweeper_stands_down_on_active_redis_jobs(results_col):
    """
    Scenario: MongoDB shows a job is 'alignment' and it's 3 hours old,
    BUT Redis returns an active job object (heavy tree math is still chugging).
    Expectation: Sweeper stands down and leaves the DB completely untouched.
    """
    results_col.database.results = results_col
    
    # Arrange
    stale_time = datetime.now(timezone.utc) - timedelta(hours=3)
    orphaned_doc = {
        "_id": STALE_RESULT_ID,
        "status": "alignment",
        "created_at": stale_time,
    }
    results_col.find.return_value = [orphaned_doc]
    mock_redis_conn = MagicMock()

    # Act
    with (
        patch("utils.sweeper.Queue") as mock_queue_cls,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError("Stop Loop")),
    ):
        # Mock Redis returning a healthy, active job instance
        mock_active_job = MagicMock()
        mock_active_job.get_status.return_value = "started"
        mock_queue_cls.return_value.fetch_job.return_value = mock_active_job

        try:
            import asyncio

            asyncio.run(start_mongodb_sweeper(results_col.database, mock_redis_conn))
        except InterruptedError:
            pass

    # Assert: MongoDB collection fixture was NEVER altered
    results_col.update_one.assert_not_called()

def test_sweeper_stands_down_on_redis_connection_error(results_col):
    """
    Scenario: MongoDB shows an old job, but checking Redis throws a connection drop error.
    Expectation: Fail-safe kicks in, is_truly_dead stays False, and Mongo isn't touched.
    """
    results_col.database.results = results_col
    
    # Arrange
    stale_time = datetime.now(timezone.utc) - timedelta(hours=3)
    orphaned_doc = {
        "_id": STALE_RESULT_ID,
        "status": "running",
        "created_at": stale_time,
    }
    results_col.find.return_value = [orphaned_doc]
    mock_redis_conn = MagicMock()

    # Act
    with (
        patch("utils.sweeper.Queue") as mock_queue_cls,
        patch("utils.sweeper.asyncio.sleep", side_effect=InterruptedError("Stop Loop")),
    ):
        # Simulate Redis choking or disconnecting entirely
        mock_queue_cls.return_value.fetch_job.side_effect = ConnectionError(
            "Redis cluster unreachable"
        )

        try:
            import asyncio

            asyncio.run(start_mongodb_sweeper(results_col.database, mock_redis_conn))
        except InterruptedError:
            pass

    # Assert: Sweeper safely aborted execution to avoid the split-brain overwrite bug
    results_col.update_one.assert_not_called()
