import asyncio
import logging
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from rq import Queue
from redis import Redis

STALE_TIMEOUT_THRESHOLD = timedelta(hours=2, minutes=30)
LOOP_INTERVAL_SECONDS = 60 * 10


async def start_mongodb_sweeper(db, redis_connection: Redis, uvicorn_logger=None):
    """
    An infinite loop background task that cleans up stuck pipeline jobs
    by cross-referencing MongoDB and Redis.
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # I WILL GET MY STUPID LOGGING TO SHOW UP HAAAAA
    def log_to_both(level: str, msg: str):
        """Dynamically routes the log message to both local and uvicorn logs if available."""
        getattr(logger, level)(msg)
        if uvicorn_logger:
            getattr(uvicorn_logger, level)(msg)
    def info(msg: str):     log_to_both("info", msg)
    def warning(msg: str):  log_to_both("warning", msg)
    def error(msg: str):    log_to_both("error", msg)
    def critical(msg: str): log_to_both("critical", msg)

    info("[Sweeper] Background task initialized successfully.")

    while True:
        try:
            info("[Sweeper] Sweeper run started...")
            cutoff_time = datetime.now(timezone.utc) - STALE_TIMEOUT_THRESHOLD
            active_statuses = [
                "pending", "running", "queued",
                "climatic_trees", "alignement", "alignment",
                "genetic_trees", "output",
            ]
            query = {
                "status": {"$in": active_statuses},
                "created_at": {"$lt": cutoff_time},
            }
            stale_jobs = list(db.results.find(query))

            if not stale_jobs:
                info("[Sweeper] Found no orphaned jobs")
            else:
                info(f"[Sweeper] Found {len(stale_jobs)} potential orphaned jobs to verify...")

                for doc in stale_jobs:
                    result_id = str(doc["_id"])
                    is_truly_dead = False

                    try:
                        rq_job = Queue(connection=redis_connection).fetch_job(result_id)
                        if rq_job is None:
                            # If it doesn't exist in Redis at all, it's an absolute ghost
                            warning(f"[Sweeper] Job {result_id} missing from Redis completely. Declaring dead.")
                            is_truly_dead = True
                        elif rq_job.get_status() in ["failed", "stopped"]:
                            # Redis knows it died, but MongoDB never got the memo
                            warning(f"[Sweeper] Job {result_id} is marked '{rq_job.get_status()}' in Redis. Syncing Mongo.")
                            is_truly_dead = True
                        else:
                            # The job is still safely registered in Redis and processing normally
                            info(f"[Sweeper] Job {result_id} is still actively tracked by Redis. Standing down.")

                    except Exception as redis_err:
                        error(f"[Sweeper] Error checking Redis for job {result_id}: {redis_err}")
                        # If we cannot contact Redis, we'll just leave the task be and check later
                        is_truly_dead = False

                    if is_truly_dead:
                        info(f"[Sweeper] Cleaning up and resetting MongoDB document: {result_id}")
                        cleanup_update = {
                            "$set": {
                                "status": "error",
                                "error_message": "Job automatically terminated: Execution exceeded maximum execution time or worker disconnected unexpectedly.",
                                "msaSet": None,
                                "genetic_trees": None,
                                "climatic_trees": None,
                                "output": None,
                            }
                        }

                        db.results.update_one(
                            {"_id": ObjectId(result_id)}, cleanup_update
                        )

        except Exception as global_err:
            critical(f"[Sweeper] Critical failure in background loop exception: {global_err}")

        info("[Sweeper] Sweeper run finished")
        await asyncio.sleep(LOOP_INTERVAL_SECONDS)
