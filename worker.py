"""
RQ worker entry point for iPhyloGeoBackend.

Adds iPhyloGeo/apps/ to sys.path so the worker resolves the same module
paths that the FastAPI server uses.

Usage:
    python worker.py
"""

import warnings
warnings.filterwarnings("ignore", message=r"The Bio\.Application modules")

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_IPHYLOGEO_ROOT = _HERE.parent / "iPhyloGeo"
_APPS_DIR = _IPHYLOGEO_ROOT / "apps"

if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

# Keep CWD consistent with the FastAPI server so relative paths work
os.chdir(_IPHYLOGEO_ROOT)

from dotenv import load_dotenv
load_dotenv(_HERE / ".env")

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
    print(f"[Worker] Python path includes: {_APPS_DIR}")

    if is_windows:
        class _WindowsWorker(SimpleWorker):
            death_penalty_class = _NoopDeathPenalty

        worker = _WindowsWorker(queues, connection=conn)
        worker.work()
    else:
        worker = Worker(queues, connection=conn)
        worker.work(with_scheduler=True)
