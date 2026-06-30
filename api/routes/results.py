"""
Results endpoints.

GET    /api/results                     → list all results
GET    /api/results/{id}                → single result
DELETE /api/results/{id}                → delete
GET    /api/results/{id}/download       → Excel file
POST   /api/results/{id}/email          → send results-ready email
"""

import io
import logging
from typing import Any

import pandas as pd
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from typing import Literal
from pydantic import BaseModel

import db.controllers.results as results_ctrl
import utils.mail as mail
from utils.utils import COOKIE_NAME, make_cookie

import redis_client

router = APIRouter(prefix="/api/results", tags=["results"])

logger = logging.getLogger(__name__)


def _serialize(obj: Any) -> Any:
    """Recursively convert MongoDB types to JSON-serialisable equivalents."""
    if isinstance(obj, ObjectId):
        return str(obj)
    if hasattr(obj, "isoformat"):  # datetime
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    return obj


@router.get("")
async def list_results(request: Request, limit: int = 50, skip: int = 0, ids: str = Query("")):
    try:
        cookie_ids = [i for i in (request.cookies.get(COOKIE_NAME) or "").split(".") if i]
        param_ids = [i for i in ids.split(",") if i]
        all_ids = list(dict.fromkeys(cookie_ids + param_ids))
        result = results_ctrl.get_all_results(ids=all_ids, limit=limit, skip=skip)
        return {
            "data": [_serialize(r) for r in result["data"]],
            "total": result["total"],
            "skip": skip,
            "limit": limit,
        }
    except Exception as exc:
        logger.exception("Failed to list results")
        raise HTTPException(500, "Internal server error") from exc


@router.get("/{result_id}")
async def get_result(result_id: str, request: Request, response: Response):
    try:
        result = results_ctrl.get_result(result_id)
        if not result:
            raise HTTPException(404, "Result not found")
        make_cookie(result_id, request.cookies.get(COOKIE_NAME), response)
        return _serialize(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get result")
        raise HTTPException(500, "Internal server error") from exc


@router.delete("/{result_id}", status_code=204)
async def delete_result(result_id: str):
    try:
        results_ctrl.delete_result(result_id)
    except Exception as exc:
        logger.exception("Failed to delete result")
        raise HTTPException(500, "Internal server error") from exc


@router.get("/{result_id}/download")
async def download_result(result_id: str):
    try:
        result = results_ctrl.get_result(result_id)
        if not result:
            raise HTTPException(404, "Result not found")

        output = result.get("output")
        if not output:
            raise HTTPException(404, "No output data available for this result yet")

        df = pd.DataFrame(output)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)

        name = result.get("name", result_id)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to download result")
        raise HTTPException(500, "Internal server error") from exc


class EmailRequest(BaseModel):
    email: str
    lang: Literal["en", "fr", "es"] = "en"

def rate_limit_emails(request: Request):
    WINDOW = 60  # 1 minute
    LIMIT = 10
    BAN_TIME = 20 * 60  # 20 minutes
    r = redis_client.get_redis()

    ip = request.client.host
    count_key = f"email_count:{ip}"
    ban_key = f"email_ban:{ip}"

    if r.get(ban_key):
        raise HTTPException(429, "Temporarily banned. Try again later.")

    count = int(r.incr(count_key))
    r.expire(count_key, WINDOW, nx=True)

    if count > LIMIT:
        r.delete(count_key)
        r.setex(ban_key, BAN_TIME, 1)
        raise HTTPException(429, "Too many requests. You are now temporarily banned.")
    
@router.post("/{result_id}/email", status_code=202)
async def email_result(result_id: str, req: EmailRequest, request: Request, background_tasks: BackgroundTasks):
    try:
        rate_limit_emails(request)
        error_str = mail.verify_email_address(req.email)
        if error_str is not None:
            raise HTTPException(400, error_str)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to validate email")
        raise HTTPException(500, "Internal server error") from exc

    results_url = f"/results?id={result_id}"
    background_tasks.add_task(mail.send_results_ready_email, req.email, results_url, req.lang)
    return {"message": "Email queued"}
