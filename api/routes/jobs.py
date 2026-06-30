"""
Job management endpoints.

POST /api/jobs                      → create result + enqueue pipeline → { result_id }
GET  /api/jobs/{result_id}/status   → { status, progress, ... }
"""

import io
import json
import logging
from typing import Literal, Optional

import pandas as pd
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

import db.controllers.files as files_ctrl
import db.controllers.results as results_ctrl
import utils.background_tasks as background_tasks
from db.db_validator import files_db
from utils.utils import COOKIE_NAME, make_cookie

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

logger = logging.getLogger(__name__)


class JobRequest(BaseModel):
    climatic_file_id: str
    genetic_file_id: Optional[str] = None
    aligned_genetic_file_id: Optional[str] = None
    genetic_tree_file_id: Optional[str] = None
    climatic_params: Optional[dict] = None
    genetic_params: Optional[dict] = None
    name: str = "result"
    email: Optional[str] = None
    lang: Literal["en", "fr", "es"] = "en"
    temporary: bool = False


def _get_raw_file(file_id: str) -> dict:
    """Fetch a raw MongoDB file document (bypasses parse_document for non-csv/fasta types)."""
    doc = files_db.find_one({"_id": ObjectId(file_id)})
    if not doc:
        raise HTTPException(404, f"File {file_id} not found")
    return doc


@router.post("")
async def create_job(req: JobRequest, request: Request, response: Response):
    try:
        # ── Retrieve climatic data ────────────────────────────────────────────
        # Bypass str_csv_to_df (which skips row 0 assuming it's a header)
        # and read the stored column-oriented JSON directly.
        raw_climatic = _get_raw_file(req.climatic_file_id)
        climatic_file: str = pd.read_json(
            io.StringIO(json.dumps(raw_climatic["file"]))
        ).to_json()

        # ── Retrieve genetic data (exactly one variant) ───────────────────────
        genetic_file = None
        aligned_genetic_file = None
        genetic_tree_file = None

        if req.genetic_file_id:
            genetic_doc = files_ctrl.get_files_by_id(req.genetic_file_id)
            genetic_file = files_ctrl.fasta_to_str(genetic_doc["file"])

        elif req.aligned_genetic_file_id:
            raw = _get_raw_file(req.aligned_genetic_file_id)
            aligned_genetic_file = json.dumps(raw["file"])

        elif req.genetic_tree_file_id:
            raw = _get_raw_file(req.genetic_tree_file_id)
            genetic_tree_file = json.dumps(raw["file"])

        # ── Build files_ids for persistent storage ────────────────────────────
        files_ids: dict = {}
        result_type: list = ["climatic"]

        if not req.temporary:
            files_ids["climatic_files_id"] = req.climatic_file_id
            if req.genetic_file_id:
                files_ids["genetic_files_id"] = req.genetic_file_id
                result_type.append("genetic")
            elif req.aligned_genetic_file_id:
                files_ids["aligned_genetic_files_id"] = req.aligned_genetic_file_id
                result_type.append("genetic")
            elif req.genetic_tree_file_id:
                files_ids["genetic_tree_files_id"] = req.genetic_tree_file_id
                result_type.append("genetic")

        # ── Create result record ──────────────────────────────────────────────
        result_payload = {
            "status": "pending",
            "name": req.name,
            "result_type": result_type,
        }
        if req.climatic_params:
            result_payload["climatic_params"] = req.climatic_params
        if req.genetic_params:
            result_payload["genetic_params"] = req.genetic_params
        result_payload.update(files_ids)

        if req.temporary:
            result_id = results_ctrl.create_temp_result(result_payload)
        else:
            result_id = results_ctrl.create_result(result_payload)

        make_cookie(str(result_id), request.cookies.get(COOKIE_NAME), response)

        # ── Enqueue pipeline ──────────────────────────────────────────────────
        background_tasks.run_pipeline_async(
            result_id=result_id,
            climatic_file=climatic_file,
            genetic_file=genetic_file,
            aligned_genetic_file=aligned_genetic_file,
            genetic_tree_file=genetic_tree_file,
            params_climatic=req.climatic_params,
            email=req.email,
            lang=req.lang,
        )

        return {"result_id": str(result_id)}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create job")
        raise HTTPException(500, "Internal server error") from exc


@router.get("/{result_id}/status")
async def get_job_status(result_id: str):
    try:
        return background_tasks.get_task_status(result_id)
    except Exception as exc:
        logger.exception("Failed to get job status")
        raise HTTPException(500, "Internal server error") from exc
