"""
File upload endpoints.

POST /api/upload/climatic                  → CSV or Excel  → { file_id }
POST /api/upload/genetic                   → FASTA         → { file_id }
POST /api/upload/aligned                   → JSON / FASTA  → { file_id }
POST /api/upload/tree                      → JSON          → { file_id }
GET  /api/upload/climatic/{file_id}/preview → { columns, rows }
GET  /api/upload/genetic/{file_id}/preview  → { sequences: {name: seq} }
"""

import io
import json

import pandas as pd
from Bio import SeqIO
from bson import ObjectId
from fastapi import APIRouter, File, HTTPException, UploadFile

import db.controllers.files as files_ctrl
from db.db_validator import files_db

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/climatic")
async def upload_climatic(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename or ""

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(400, "Only CSV or Excel (.csv / .xlsx / .xls) files are allowed")

        # Store as JSON-encoded string; save_files() will decode it to a dict
        file_data = {"file_name": filename, "file": df.to_json(), "type": "climatic"}
        file_id = files_ctrl.save_files([file_data])
        return {"file_id": str(file_id)}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to process climatic file: {exc}") from exc


@router.post("/genetic")
async def upload_genetic(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename or ""

    try:
        if not filename.endswith(".fasta"):
            raise HTTPException(400, "Only FASTA (.fasta) files are allowed")

        fasta_str = content.decode("utf-8")
        fasta_dict = files_ctrl.fasta_to_str(
            SeqIO.parse(io.StringIO(fasta_str), "fasta")
        )

        file_data = {"file_name": filename, "file": fasta_dict, "type": "genetic"}
        file_id = files_ctrl.save_files([file_data])
        return {"file_id": str(file_id)}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to process genetic file: {exc}") from exc


@router.post("/aligned")
async def upload_aligned(file: UploadFile = File(...)):
    """Accept a pre-aligned genetic file (aphylogeo JSON export or FASTA)."""
    content = await file.read()
    filename = file.filename or ""

    try:
        if not (filename.endswith(".json") or filename.endswith(".fasta")):
            raise HTTPException(400, "Only JSON (.json) or FASTA (.fasta) files are allowed")

        data_str = content.decode("utf-8")

        if filename.endswith(".json"):
            parsed = json.loads(data_str)
            stored = parsed if isinstance(parsed, dict) else {"content": data_str}
        else:
            # FASTA aligned: store as dict {seq_name: sequence}
            stored = files_ctrl.fasta_to_str(SeqIO.parse(io.StringIO(data_str), "fasta"))

        file_data = {"file_name": filename, "file": stored, "type": "aligned_genetic"}
        file_id = files_ctrl.save_files([file_data])
        return {"file_id": str(file_id)}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to process aligned file: {exc}") from exc


@router.post("/tree")
async def upload_tree(file: UploadFile = File(...)):
    """Accept a pre-computed genetic tree file (aphylogeo JSON export)."""
    content = await file.read()
    filename = file.filename or ""

    try:
        if not filename.endswith(".json"):
            raise HTTPException(400, "Only JSON (.json) files are allowed")

        parsed = json.loads(content.decode("utf-8"))
        stored = parsed if isinstance(parsed, dict) else {"content": content.decode("utf-8")}

        file_data = {"file_name": filename, "file": stored, "type": "genetic_tree"}
        file_id = files_ctrl.save_files([file_data])
        return {"file_id": str(file_id)}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to process tree file: {exc}") from exc


@router.get("/climatic/{file_id}/preview")
async def preview_climatic(file_id: str):
    """Return columns and first 200 rows of a stored climatic CSV file."""
    try:
        if not ObjectId.is_valid(file_id):
            raise HTTPException(400, "Invalid file_id")
        doc = files_db.find_one({"_id": ObjectId(file_id)})
        if not doc:
            raise HTTPException(404, "File not found")
        df = pd.DataFrame.from_dict(doc["file"])
        return {
            "columns": list(df.columns),
            "rows": df.head(200).to_dict("records"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to preview climatic file: {exc}") from exc


@router.get("/genetic/{file_id}/preview")
async def preview_genetic(file_id: str):
    """Return sequence names and first 300 characters of each sequence."""
    try:
        if not ObjectId.is_valid(file_id):
            raise HTTPException(400, "Invalid file_id")
        doc = files_db.find_one({"_id": ObjectId(file_id)})
        if not doc:
            raise HTTPException(404, "File not found")
        sequences: dict = doc.get("file", {})
        # Truncate to first 300 chars for alignment preview
        preview = {name: str(seq)[:300] for name, seq in sequences.items()}
        return {"sequences": preview, "full_length": max((len(str(s)) for s in sequences.values()), default=0)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to preview genetic file: {exc}") from exc
