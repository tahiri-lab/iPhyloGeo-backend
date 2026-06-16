"""
Settings endpoints.

GET /api/settings   → current genetic_settings_file.json
PUT /api/settings   → overwrite genetic_settings_file.json (validated)
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from enums import (
    AlignmentMethod,
    DistanceMethod,
    FitMethod,
    MantelTestMethod,
    PreprocessingToggle,
    SimilarityMethod,
    StatisticalTest,
    TreeType,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "genetic_settings_file.json"


class SettingsModel(BaseModel):
    bootstrap_threshold: int = Field(ge=0)
    dist_threshold: int = Field(ge=0)
    window_size: int = Field(ge=1)
    step_size: int = Field(ge=1)
    alignment_method: AlignmentMethod
    distance_method: DistanceMethod
    fit_method: FitMethod
    tree_type: TreeType
    rate_similarity: int = Field(ge=0, le=100)
    method_similarity: SimilarityMethod
    preprocessing_genetic: PreprocessingToggle
    preprocessing_climatic: PreprocessingToggle
    preprocessing_threshold_genetic: float = Field(ge=0)
    preprocessing_threshold_climatic: float = Field(ge=0)
    correlation_climatic_enabled: PreprocessingToggle
    correlation_threshold_climatic: float = Field(ge=0, le=1)
    permutations_mantel_test: int = Field(ge=1)
    permutations_protest: int = Field(ge=1)
    mantel_test_method: MantelTestMethod
    statistical_test: StatisticalTest


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
async def update_settings(settings: SettingsModel):
    try:
        data = settings.model_dump()
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data
    except Exception as exc:
        raise HTTPException(500, f"Failed to write settings: {exc}") from exc
