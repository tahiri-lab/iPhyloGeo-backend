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
import logging

import pandas as pd
from Bio import SeqIO
from bson import ObjectId
from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

import db.controllers.files as files_ctrl
from db.db_validator import files_db

from utils.utils import is_file_valid

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/climatic")
async def upload_climatic(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename or ""

    try:
        ext = is_file_valid(
            filename,
            content,
            [".csv", ".xlsx", ".xls"],
            ["text/csv",
             "text/plain",
             "application/vnd.ms-excel",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "application/zip",
             "application/x-zip-compressed"],
            50*1024*1024)

        readers = {
            ".csv": lambda c: pd.read_csv(io.BytesIO(c)),
            ".xlsx": lambda c: pd.read_excel(io.BytesIO(c)),
            ".xls": lambda c: pd.read_excel(io.BytesIO(c)),
        }
        reader = readers.get(ext)

        if reader is None:
            raise HTTPException(400, "Only CSV or Excel (.csv / .xlsx / .xls) files are allowed")

        df = reader(content)

        file_data = {"file_name": filename, "file": df.to_json(), "type": "climatic"}
        file_id = files_ctrl.save_files([file_data])
        return {"file_id": str(file_id)}

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to process climatic file")
        raise HTTPException(500, "Internal server error") from exc


@router.post("/genetic")
async def upload_genetic(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename or ""

    try:
        ext = is_file_valid(
            filename,
            content,
            [".fasta"],
            ["text/plain"],
            50*1024*1024)

        readers = {
            ".fasta": lambda s: files_ctrl.fasta_to_str(SeqIO.parse(io.StringIO(s), "fasta")),
        }
        reader = readers.get(ext)

        if reader is None:
            raise HTTPException(400, "Only FASTA (.fasta) files are allowed")

        fasta_str = content.decode("utf-8")
        fasta_dict = reader(fasta_str)

        file_data = {"file_name": filename, "file": fasta_dict, "type": "genetic"}
        file_id = files_ctrl.save_files([file_data])
        return {"file_id": str(file_id)}

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to process genetic file")
        raise HTTPException(500, "Internal server error") from exc


@router.post("/aligned")
async def upload_aligned(file: UploadFile = File(...)):
    """Accept a pre-aligned genetic file (aphylogeo JSON export or FASTA)."""
    content = await file.read()
    filename = file.filename or ""

    try:
        ext = is_file_valid(
            filename,
            content,
            [".fasta", ".json"],
            ["text/plain",
             "application/json"],
            50*1024*1024)

        def handle_json(s):
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else {"content": s}

        readers = {
            ".json": lambda s: handle_json(s),
            ".fasta": lambda s: files_ctrl.fasta_to_str(SeqIO.parse(io.StringIO(s), "fasta")),
        }
        reader = readers.get(ext)

        if reader is None:
            raise HTTPException(400, "Only JSON (.json) or FASTA (.fasta) files are allowed")

        data_str = content.decode("utf-8")
        stored = reader(data_str)

        file_data = {"file_name": filename, "file": stored, "type": "aligned_genetic"}
        file_id = files_ctrl.save_files([file_data])
        return {"file_id": str(file_id)}

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to process aligned file")
        raise HTTPException(500, "Internal server error") from exc


@router.post("/tree")
async def upload_tree(file: UploadFile = File(...)):
    """Accept a pre-computed genetic tree file (aphylogeo JSON export)."""
    content = await file.read()
    filename = file.filename or ""

    try:
        ext = is_file_valid(
            filename,
            content,
            [".json"],
            ["application/json"],
            50*1024*1024)

        def handle_json(s):
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else {"content": s}

        readers = {
            ".json": lambda s: handle_json(s),
        }
        reader = readers.get(ext)

        if reader is None:
            raise HTTPException(400, "Only JSON (.json) files are allowed")

        data_str = content.decode("utf-8")
        stored = reader(data_str)

        file_data = {"file_name": filename, "file": stored, "type": "genetic_tree"}
        file_id = files_ctrl.save_files([file_data])
        return {"file_id": str(file_id)}

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to process tree file")
        raise HTTPException(500, "Internal server error") from exc


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
        logger.exception("Failed to preview climatic file")
        raise HTTPException(500, "Internal server error") from exc


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
        preview = {name: str(seq)[:300] for name, seq in sequences.items()}
        return {"sequences": preview, "full_length": max((len(str(s)) for s in sequences.values()), default=0)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to preview genetic file")
        raise HTTPException(500, "Internal server error") from exc
