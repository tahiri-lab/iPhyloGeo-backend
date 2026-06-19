import asyncio
import logging
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from rq.job import Job
from rq import Worker
from db.controllers.results import results_db
import redis_client
from rq.exceptions import NoSuchJobError

# TODO this may not be the exact right thresholds depending on what kind of usage we expect for our app
SUSPICIOUS_THRESHOLD = timedelta(hours=1, minutes=0)
STALE_THRESHOLD = timedelta(hours=24, minutes=0)
LOOP_INTERVAL_SECONDS = 60 * 30 # 30 minutes

redis_connection = redis_client.get_redis()

async def start_mongodb_sweeper(uvicorn_logger=None):
    """
    An infinite loop background task that cleans up stuck pipeline jobs
    by cross-referencing MongoDB and Redis.
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    def log_to_both(level: str, msg: str):
        """Dynamically routes the log message to both local and uvicorn logs if available."""
        getattr(logger, level)(msg)
        if uvicorn_logger:
            getattr(uvicorn_logger, level)(f"[Sweeper] {msg}")
    def info(msg: str):     log_to_both("info", msg)
    def warning(msg: str):  log_to_both("warning", msg)
    def error(msg: str):    log_to_both("error", msg)
    def critical(msg: str): log_to_both("critical", msg)

    info("Background task initialized successfully.")

    while True:
        try:
            info("Sweeper run started...")
            active_statuses = [
                "pending", "running", "queued",
                "climatic_trees", "alignement", "alignment",
                "genetic_trees", "output",
            ]
            query = {
                "status": {"$in": active_statuses},
            }
            stale_jobs = list(results_db.find(query))

            if not stale_jobs:
                info("Found no orphaned jobs")
            else:
                info(f"Found {len(stale_jobs)} potential orphaned jobs to verify...")

                workers = Worker.all(connection=redis_connection)
                print(workers)
                for doc in stale_jobs:
                    result_id = str(doc["_id"])
                    has_been = (datetime.now(timezone.utc)
                        - doc["created_at"].replace(tzinfo=timezone.utc))
                    is_truly_dead = False

                    try:
                        rq_job = Job.fetch(str(result_id), connection=redis_connection)
                        status = rq_job.get_status()

                        if status == "finished":
                            info(
                                f"Job {result_id} is finished in Redis; marking result as complete."
                            )
                            results_db.update_one(
                                {"_id": ObjectId(result_id)},
                                {
                                    "$set": {
                                        "status": "complete",
                                        "is_taking_very_long": False,
                                    }
                                },
                            )
                            continue

                        if (
                            status == "started"
                            and str(doc["status"]) not in ["pending", "queued"]
                            and not any(w.name == rq_job.worker_name for w in workers)
                        ):
                            warning(f"Job {result_id} is marked 'started' in Redis and the result has some work done, but there is no worker.")
                            is_truly_dead = True
                        elif status in ["failed", "stopped", "canceled"]:
                            warning(f"Job {result_id} is marked '{status}' in Redis.")
                            is_truly_dead = True
                        elif has_been > STALE_THRESHOLD:
                            warning(
                                f"Job {result_id} has been running for {has_been} and has exceeded the stale threshold."
                            )
                            is_truly_dead = True
                        elif has_been > SUSPICIOUS_THRESHOLD:
                            info(f"Job {result_id} has been running for {has_been} and has exceeded the suspicious threshold. Marking as taking a very long time...")
                            cleanup_update = {
                                "$set": {
                                    "is_taking_very_long": True,
                                }
                            }

                            results_db.update_one(
                                {
                                    "_id": ObjectId(result_id),
                                    "is_taking_very_long": {"$ne": True},
                                },
                                cleanup_update,
                            )

                    except NoSuchJobError:
                        warning(f"Job {result_id} missing from Redis completely.")
                        is_truly_dead = True

                    except Exception as redis_err:
                        error(f"Error checking Redis for job {result_id}: {redis_err}")

                    if is_truly_dead:
                        info(f"Updating the status of the result to error: {result_id}")
                        cleanup_update = {
                            "$set": {
                                "status": "error",
                            }
                        }

                        results_db.update_one(
                            {"_id": ObjectId(result_id)}, cleanup_update
                        )

        except asyncio.CancelledError:
            info("Sweeper task cancelled")
            raise
        except Exception as global_err:
            critical(f"Critical failure in background loop exception: {global_err}")

        info("Sweeper run finished")
        await asyncio.sleep(LOOP_INTERVAL_SECONDS)
