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
import redis_client

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
    r = redis_client.get_redis()

    queues = [Queue(connection=r)]

    is_windows = sys.platform == "win32"
    print(f"[Worker] Platform: {'Windows' if is_windows else sys.platform}")
    print(f"[Worker] Redis: {redis_client.redis_url}")

    if is_windows:
        class _WindowsWorker(SimpleWorker):
            death_penalty_class = _NoopDeathPenalty

        worker = _WindowsWorker(queues, connection=r)
        worker.work()
    else:
        worker = Worker(queues, connection=r)
        worker.work(with_scheduler=True)
