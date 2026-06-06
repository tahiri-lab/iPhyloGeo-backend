"""
iPhyloGeo FastAPI backend.

Start:
    uvicorn main:app --reload --port 8000
"""

import os
import warnings
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
import logging

warnings.filterwarnings("ignore", message=r"The Bio\.Application modules")

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.upload import router as upload_router
from api.routes.jobs import router as jobs_router
from api.routes.results import router as results_router
from api.routes.settings import router as settings_router

from utils.sweeper import start_mongodb_sweeper

@asynccontextmanager
async def lifespan(app: FastAPI):
    uvicorn_logger = logging.getLogger("uvicorn.error")
    sweeper_task = asyncio.create_task(start_mongodb_sweeper(uvicorn_logger))
    yield
    sweeper_task.cancel()

app = FastAPI(title="iPhyloGeo API", version="1.0.0", lifespan=lifespan)

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
