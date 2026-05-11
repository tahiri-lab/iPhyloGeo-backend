"""
RQ worker entry point for iPhyloGeoBackend.

Usage:
    python worker.py
"""

import warnings
warnings.filterwarnings("ignore", message=r"The Bio\.Application modules")

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from redis import Redis
from rq import Queue
from rq.worker import SimpleWorker, Worker


class _NoopDeathPenalty:
    """No-op death penalty for Windows (no SIGALRM)."""

    def __init__(self, timeout, exception=None, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cancel(self):
        pass


if __name__ == "__main__":
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    conn = Redis.from_url(redis_url)
    queues = [Queue(connection=conn)]

    is_windows = sys.platform == "win32"
    print(f"[Worker] Platform: {'Windows' if is_windows else sys.platform}")
    print(f"[Worker] Redis: {redis_url}")

    if is_windows:
        class _WindowsWorker(SimpleWorker):
            death_penalty_class = _NoopDeathPenalty

        worker = _WindowsWorker(queues, connection=conn)
        worker.work()
    else:
        worker = Worker(queues, connection=conn)
        worker.work(with_scheduler=True)
