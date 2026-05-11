"""
Settings endpoints.

GET /api/settings   → current genetic_settings_file.json
PUT /api/settings   → overwrite genetic_settings_file.json
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/settings", tags=["settings"])

_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "genetic_settings_file.json"


@router.get("")
async def get_settings():
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(404, "Settings file not found")
    except Exception as exc:
        raise HTTPException(500, f"Failed to read settings: {exc}") from exc


@router.put("")
async def update_settings(settings: dict):
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return settings
    except Exception as exc:
        raise HTTPException(500, f"Failed to write settings: {exc}") from exc
