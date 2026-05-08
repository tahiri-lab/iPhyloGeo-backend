"""
iPhyloGeo FastAPI backend.

Reuses the existing Python modules in ../iPhyloGeo/apps/ (db, utils, enums)
without duplicating code. The CWD is changed to iPhyloGeo/ so that relative
paths inside those modules (genetic_settings_file.json, aphylogeo/bin/tmp)
resolve correctly.

Start:
    uvicorn main:app --reload --port 8000
"""

import sys
import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=r"The Bio\.Application modules")

# ── Path setup (must happen before any app-module imports) ────────────────────
_HERE = Path(__file__).resolve().parent
_IPHYLOGEO_ROOT = _HERE.parent / "iPhyloGeo"
_IPHYLOGEO_APPS = _IPHYLOGEO_ROOT / "apps"

if str(_IPHYLOGEO_APPS) not in sys.path:
    sys.path.insert(0, str(_IPHYLOGEO_APPS))

# Change CWD so relative paths in the legacy code resolve correctly:
#   - genetic_settings_file.json (used in utils.py)
#   - aphylogeo/bin/tmp          (used in create_genetic_trees)
os.chdir(_IPHYLOGEO_ROOT)

# ── Environment ───────────────────────────────────────────────────────────────
from dotenv import load_dotenv

load_dotenv(_HERE / ".env")

# ── FastAPI app ───────────────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.upload import router as upload_router
from api.routes.jobs import router as jobs_router
from api.routes.results import router as results_router
from api.routes.settings import router as settings_router

app = FastAPI(title="iPhyloGeo API", version="1.0.0")

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(jobs_router)
app.include_router(results_router)
app.include_router(settings_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
