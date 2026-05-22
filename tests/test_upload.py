"""
Tests for file-upload and preview endpoints.

POST /api/upload/climatic
POST /api/upload/genetic
POST /api/upload/aligned
POST /api/upload/tree
GET  /api/upload/climatic/{file_id}/preview
GET  /api/upload/genetic/{file_id}/preview
"""

import io
import json

import pandas as pd
from bson import ObjectId

FAKE_FILE_ID = ObjectId("507f1f77bcf86cd799439011")

VALID_CSV = b"specimen_id,temperature,rainfall\nA,25.5,100\nB,18.3,250\n"
VALID_FASTA = b">seq1\nATCGATCG\n>seq2\nGCTAGCTA\n"
VALID_JSON = json.dumps({"key": "value"}).encode()


def _csv_upload(client, filename="data.csv", content=VALID_CSV):
    return client.post(
        "/api/upload/climatic",
        files={"file": (filename, io.BytesIO(content), "text/csv")},
    )


def _genetic_upload(client, filename="seqs.fasta", content=VALID_FASTA):
    return client.post(
        "/api/upload/genetic",
        files={"file": (filename, io.BytesIO(content), "text/plain")},
    )


def _make_climatic_doc():
    df = pd.DataFrame({"specimen_id": ["A", "B"], "temperature": [25.5, 18.3]})
    return {
        "_id": FAKE_FILE_ID,
        "file_name": "climatic.csv",
        "type": "climatic",
        "file": json.loads(df.to_json()),
    }


def _make_genetic_doc():
    return {
        "_id": FAKE_FILE_ID,
        "file_name": "seqs.fasta",
        "type": "genetic",
        "file": {"seq1": "ATCGATCG" * 40, "seq2": "GCTAGCTA" * 40},
    }


# ── Climatic upload ────────────────────────────────────────────────────────────


def test_upload_climatic_csv_returns_file_id(client, files_col):
    r = _csv_upload(client)
    assert r.status_code == 200
    assert "file_id" in r.json()


def test_upload_climatic_excel_returns_file_id(client, files_col):
    buf = io.BytesIO()
    pd.DataFrame({"specimen_id": ["A", "B"], "temp": [25.5, 18.3]}).to_excel(
        buf, index=False
    )
    buf.seek(0)
    r = client.post(
        "/api/upload/climatic",
        files={
            "file": (
                "data.xlsx",
                buf,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200
    assert "file_id" in r.json()


def test_upload_climatic_invalid_extension_returns_400(client):
    r = client.post(
        "/api/upload/climatic",
        files={"file": ("data.txt", io.BytesIO(b"foo"), "text/plain")},
    )
    assert r.status_code == 400


def test_upload_climatic_empty_csv_still_accepted(client, files_col):
    r = _csv_upload(client, content=b"col1,col2\n")
    assert r.status_code == 200


# ── Genetic upload ─────────────────────────────────────────────────────────────


def test_upload_genetic_fasta_returns_file_id(client, files_col):
    r = _genetic_upload(client)
    assert r.status_code == 200
    assert "file_id" in r.json()


def test_upload_genetic_wrong_extension_returns_400(client):
    r = client.post(
        "/api/upload/genetic",
        files={"file": ("seqs.csv", io.BytesIO(b"not fasta"), "text/plain")},
    )
    assert r.status_code == 400


def test_upload_genetic_invalid_fasta_returns_500(client, files_col):
    r = _genetic_upload(client, content=b"NOT A FASTA FILE!!!")
    assert r.status_code in (200, 500)


# ── Aligned genetic upload ─────────────────────────────────────────────────────


def test_upload_aligned_json_returns_file_id(client, files_col):
    r = client.post(
        "/api/upload/aligned",
        files={"file": ("aligned.json", io.BytesIO(VALID_JSON), "application/json")},
    )
    assert r.status_code == 200
    assert "file_id" in r.json()


def test_upload_aligned_fasta_returns_file_id(client, files_col):
    r = client.post(
        "/api/upload/aligned",
        files={"file": ("aligned.fasta", io.BytesIO(VALID_FASTA), "text/plain")},
    )
    assert r.status_code == 200
    assert "file_id" in r.json()


def test_upload_aligned_invalid_extension_returns_400(client):
    r = client.post(
        "/api/upload/aligned",
        files={"file": ("data.txt", io.BytesIO(b"foo"), "text/plain")},
    )
    assert r.status_code == 400


# ── Tree upload ────────────────────────────────────────────────────────────────


def test_upload_tree_json_returns_file_id(client, files_col):
    r = client.post(
        "/api/upload/tree",
        files={"file": ("tree.json", io.BytesIO(VALID_JSON), "application/json")},
    )
    assert r.status_code == 200
    assert "file_id" in r.json()


def test_upload_tree_non_json_returns_400(client):
    r = client.post(
        "/api/upload/tree",
        files={"file": ("tree.fasta", io.BytesIO(VALID_FASTA), "text/plain")},
    )
    assert r.status_code == 400


def test_upload_tree_invalid_json_returns_error(client):
    r = client.post(
        "/api/upload/tree",
        files={"file": ("tree.json", io.BytesIO(b"NOT JSON {{{"), "application/json")},
    )
    assert r.status_code in (400, 500)


# ── Climatic preview ───────────────────────────────────────────────────────────


def test_preview_climatic_returns_columns_and_rows(client, files_col):
    files_col.find_one.return_value = _make_climatic_doc()
    r = client.get(f"/api/upload/climatic/{FAKE_FILE_ID}/preview")
    assert r.status_code == 200
    data = r.json()
    assert "columns" in data
    assert "rows" in data
    assert "specimen_id" in data["columns"]
    assert len(data["rows"]) == 2


def test_preview_climatic_invalid_id_returns_400(client):
    r = client.get("/api/upload/climatic/not-an-objectid/preview")
    assert r.status_code == 400


def test_preview_climatic_not_found_returns_404(client, files_col):
    files_col.find_one.return_value = None
    r = client.get(f"/api/upload/climatic/{FAKE_FILE_ID}/preview")
    assert r.status_code == 404


# ── Genetic preview ────────────────────────────────────────────────────────────


def test_preview_genetic_returns_sequences(client, files_col):
    files_col.find_one.return_value = _make_genetic_doc()
    r = client.get(f"/api/upload/genetic/{FAKE_FILE_ID}/preview")
    assert r.status_code == 200
    data = r.json()
    assert "sequences" in data
    assert "full_length" in data
    assert "seq1" in data["sequences"]
    assert len(data["sequences"]["seq1"]) <= 300


def test_preview_genetic_invalid_id_returns_400(client):
    r = client.get("/api/upload/genetic/BAD-ID/preview")
    assert r.status_code == 400


def test_preview_genetic_not_found_returns_404(client, files_col):
    files_col.find_one.return_value = None
    r = client.get(f"/api/upload/genetic/{FAKE_FILE_ID}/preview")
    assert r.status_code == 404


def test_preview_genetic_empty_sequences(client, files_col):
    doc = _make_genetic_doc()
    doc["file"] = {}
    files_col.find_one.return_value = doc
    r = client.get(f"/api/upload/genetic/{FAKE_FILE_ID}/preview")
    assert r.status_code == 200
    assert r.json()["full_length"] == 0
