"""
Unit tests for pure helper functions that require no database or network access.

Covered modules:
  - utils.utils         : format_card_date, to_datetime_utc, _filter_alignment_gaps
  - db.controllers.files: fasta_to_str, str_csv_to_df, df_to_str_csv
  - api.routes.results  : _serialize
  - enums               : BaseEnum.get_code, convert_settings_to_codes
  - utils.background_tasks: count_sequences, count_climatic_columns
"""

import json
from datetime import datetime, timezone

import pandas as pd
import pytest
from bson import ObjectId
from Bio.Align import MultipleSeqAlignment
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from utils.utils import format_card_date, to_datetime_utc, _filter_alignment_gaps, is_file_valid
from db.controllers.files import fasta_to_str, str_csv_to_df, df_to_str_csv
from api.routes.results import _serialize
from enums import (
    AlignmentMethod,
    DistanceMethod,
    convert_settings_to_codes,
)
from utils.background_tasks import count_sequences, count_climatic_columns


# ── format_card_date ───────────────────────────────────────────────────────────


def test_format_card_date_with_datetime_object():
    dt = datetime(2024, 3, 15)
    assert format_card_date(dt) == "15/03/2024"


def test_format_card_date_with_iso_string():
    assert format_card_date("2024-03-15T10:30:00") == "15/03/2024"


def test_format_card_date_with_utc_z_string():
    assert format_card_date("2024-03-15T00:00:00Z") == "15/03/2024"


def test_format_card_date_with_none():
    assert format_card_date(None) is None


def test_format_card_date_with_numeric_fallback():
    result = format_card_date(42)
    assert result == "42"


def test_format_card_date_with_invalid_string():
    result = format_card_date("not-a-date")
    assert isinstance(result, str)


# ── to_datetime_utc ────────────────────────────────────────────────────────────


def test_to_datetime_utc_with_none_returns_min():
    result = to_datetime_utc(None)
    assert result == datetime.min.replace(tzinfo=timezone.utc)


def test_to_datetime_utc_with_naive_datetime_adds_utc():
    naive = datetime(2024, 6, 1, 12, 0, 0)
    result = to_datetime_utc(naive)
    assert result.tzinfo == timezone.utc
    assert result.year == 2024


def test_to_datetime_utc_with_aware_datetime_converts():
    from datetime import timedelta, timezone as tz
    eastern = timezone(timedelta(hours=-5))
    aware = datetime(2024, 6, 1, 12, 0, 0, tzinfo=eastern)
    result = to_datetime_utc(aware)
    assert result.tzinfo == timezone.utc
    assert result.hour == 17  # 12:00 EST → 17:00 UTC


def test_to_datetime_utc_with_iso_string():
    result = to_datetime_utc("2024-06-01T10:00:00Z")
    assert result.tzinfo == timezone.utc
    assert result.year == 2024


def test_to_datetime_utc_with_invalid_string_returns_min():
    result = to_datetime_utc("not-a-date")
    assert result == datetime.min.replace(tzinfo=timezone.utc)


# ── fasta_to_str ───────────────────────────────────────────────────────────────


def _make_fasta_iter(entries: dict):
    """Build a SeqIO-compatible iterator from a {id: seq} dict."""
    from Bio.SeqRecord import SeqRecord
    from Bio.Seq import Seq

    return (SeqRecord(Seq(seq), id=sid, description="") for sid, seq in entries.items())


def test_fasta_to_str_converts_to_plain_strings():
    entries = {"seq1": "ATCG", "seq2": "GCTA"}
    result = fasta_to_str(_make_fasta_iter(entries))
    assert result == {"seq1": "ATCG", "seq2": "GCTA"}


def test_fasta_to_str_preserves_all_sequences():
    entries = {f"s{i}": "A" * i for i in range(1, 6)}
    result = fasta_to_str(_make_fasta_iter(entries))
    assert set(result.keys()) == set(entries.keys())
    assert all(isinstance(v, str) for v in result.values())


def test_fasta_to_str_empty_input():
    result = fasta_to_str(iter([]))
    assert result == {}


# ── str_csv_to_df ──────────────────────────────────────────────────────────────


def test_str_csv_to_df_skips_header_row():
    # str_csv_to_df expects a column-oriented dict and skips row index "0"
    data = {"col1": {"0": "header_val", "1": "A", "2": "B"}}
    df = str_csv_to_df(data)
    assert len(df) == 2  # rows 1 and 2; row 0 is skipped


def test_str_csv_to_df_numeric_conversion():
    data = {"value": {"0": "value", "1": "10", "2": "20"}}
    df = str_csv_to_df(data)
    assert df["value"].dtype in (int, float, "int64", "float64")


def test_str_csv_to_df_mixed_column_stays_string():
    data = {"mixed": {"0": "mixed", "1": "abc", "2": "def"}}
    df = str_csv_to_df(data)
    assert df["mixed"].dtype == object


# ── df_to_str_csv ──────────────────────────────────────────────────────────────


def test_df_to_str_csv_first_row_is_header():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    result = df_to_str_csv(df)
    assert result[0] == ["a", "b"]


def test_df_to_str_csv_returns_list_of_lists():
    df = pd.DataFrame({"x": [10, 20]})
    result = df_to_str_csv(df)
    assert isinstance(result, list)
    assert all(isinstance(row, list) for row in result)
    assert len(result) == 3  # header + 2 data rows


# ── _serialize ─────────────────────────────────────────────────────────────────


def test_serialize_objectid_becomes_string():
    oid = ObjectId("507f1f77bcf86cd799439011")
    assert _serialize(oid) == "507f1f77bcf86cd799439011"


def test_serialize_datetime_becomes_isoformat():
    dt = datetime(2024, 1, 15, 10, 30, 0)
    result = _serialize(dt)
    assert "2024-01-15" in result


def test_serialize_nested_dict():
    oid = ObjectId("507f1f77bcf86cd799439011")
    data = {"_id": oid, "name": "test"}
    result = _serialize(data)
    assert result["_id"] == "507f1f77bcf86cd799439011"
    assert result["name"] == "test"


def test_serialize_list_with_objectids():
    oids = [ObjectId("507f1f77bcf86cd799439011"), ObjectId("507f1f77bcf86cd799439012")]
    result = _serialize(oids)
    assert result == ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"]


def test_serialize_plain_value_unchanged():
    assert _serialize(42) == 42
    assert _serialize("hello") == "hello"
    assert _serialize(None) is None


# ── enums ──────────────────────────────────────────────────────────────────────


def test_alignment_method_get_code_known_value():
    assert AlignmentMethod.get_code("PairwiseAlign") == "1"
    assert AlignmentMethod.get_code("MUSCLE") == "2"
    assert AlignmentMethod.get_code("NoAlignment") == "0"


def test_alignment_method_get_code_unknown_returns_value():
    assert AlignmentMethod.get_code("UnknownMethod") == "UnknownMethod"


def test_distance_method_get_code():
    assert DistanceMethod.get_code("LeastSquare") == "1"
    assert DistanceMethod.get_code("All") == "0"


def test_alignment_method_choices_returns_list():
    choices = AlignmentMethod.choices()
    assert isinstance(choices, list)
    assert all("label" in c and "value" in c for c in choices)


def test_convert_settings_to_codes_transforms_known_keys():
    settings = {
        "alignment_method": "PairwiseAlign",
        "distance_method": "LeastSquare",
        "tree_type": "BioPython",
        "window_size": 100,
    }
    result = convert_settings_to_codes(settings)
    assert result["alignment_method"] == "1"
    assert result["distance_method"] == "1"
    assert result["tree_type"] == "1"
    assert result["window_size"] == 100  # non-enum keys pass through unchanged


def test_convert_settings_to_codes_does_not_mutate_input():
    settings = {"alignment_method": "MUSCLE"}
    original = settings.copy()
    convert_settings_to_codes(settings)
    assert settings == original


# ── _filter_alignment_gaps ─────────────────────────────────────────────────────


def _make_alignment(seqs: list[str]) -> MultipleSeqAlignment:
    records = [
        SeqRecord(Seq(s), id=f"seq{i}", description="")
        for i, s in enumerate(seqs)
    ]
    return MultipleSeqAlignment(records)


def test_filter_alignment_gaps_removes_gap_heavy_columns():
    # Column 2 is all gaps → should be removed at threshold 0.5
    aln = _make_alignment(["AT-G", "AT-G", "AT-G"])
    filtered = _filter_alignment_gaps(aln, threshold=0.5)
    for record in filtered:
        assert "-" not in str(record.seq)


def test_filter_alignment_gaps_keeps_low_gap_columns():
    # One gap in four sequences = 25% < 50% threshold → column kept
    aln = _make_alignment(["ATCG", "ATCG", "AT-G", "ATCG"])
    filtered = _filter_alignment_gaps(aln, threshold=0.5)
    length = filtered.get_alignment_length()
    assert length == 4


def test_filter_alignment_gaps_all_columns_removed_at_zero_threshold():
    # threshold=0 means even one gap removes the column
    aln = _make_alignment(["A-C", "AGC"])
    filtered = _filter_alignment_gaps(aln, threshold=0.0)
    assert filtered.get_alignment_length() == 2  # column 1 ('-') removed


def test_filter_alignment_gaps_preserves_sequence_count():
    aln = _make_alignment(["ATCG", "ATCG", "AT-G"])
    filtered = _filter_alignment_gaps(aln, threshold=0.9)
    assert len(list(filtered)) == 3


# ── count_sequences ────────────────────────────────────────────────────────────


def test_count_sequences_from_dict():
    genetic = {"seq1": "ATCG", "seq2": "GCTA", "seq3": "TTTT"}
    assert count_sequences(genetic) == 3


def test_count_sequences_from_string():
    fasta_str = ">seq1\nATCG\n>seq2\nGCTA\n"
    assert count_sequences(fasta_str) == 2


def test_count_sequences_empty_dict():
    assert count_sequences({}) == 0


def test_count_sequences_none():
    assert count_sequences(None) == 0


# ── count_climatic_columns ─────────────────────────────────────────────────────


def test_count_climatic_columns_from_json_string():
    df = pd.DataFrame({
        "specimen_id": ["A", "B"],
        "temperature": [25.0, 18.0],
        "rainfall": [100.0, 200.0],
    })
    result = count_climatic_columns(df.to_json())
    # Excludes first column (specimen_id)
    assert result == 2


def test_count_climatic_columns_empty_string():
    result = count_climatic_columns("")
    assert result == 0


def test_count_climatic_columns_invalid_json_returns_default():
    result = count_climatic_columns("NOT JSON")
    assert result == 2  # documented fallback

# ── file validator ───────────────────────────────────────────────────────────

def test_valid_csv(tmp_path):
    file = tmp_path / "test.csv"
    file.write_text("a,b,c\n1,2,3")

    content = file.read_bytes()

    ext = is_file_valid(
        filename="test.csv",
        content=content,
        allowed_extensions=[".csv"],
        allowed_mimetypes=["text/csv"],
        max_size_bytes=1024
    )

    assert ext == ".csv"


def test_invalid_extension(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("hello")

    content = file.read_bytes()

    with pytest.raises(ValueError) as exc:
        is_file_valid(
            filename="test.txt",
            content=content,
            allowed_extensions=[".csv"],
            allowed_mimetypes=["text/csv"],
            max_size_bytes=1024
        )

    assert "Extension" in str(exc.value)

def test_wrong_mimetype(tmp_path):
    file = tmp_path / "test.csv"
    file.write_text("not really a csv")

    content = file.read_bytes()

    # Allowed extension is .csv but mimetype will NOT be text/csv
    with pytest.raises(ValueError) as exc:
        is_file_valid(
            filename="test.csv",
            content=content,
            allowed_extensions=[".csv"],
            allowed_mimetypes=["text/csv"],
            max_size_bytes=1024
        )

    assert "Mimetype" in str(exc.value)

def test_file_too_large(tmp_path):
    file = tmp_path / "big.csv"
    file.write_text("a" * 5000)  # 5 KB

    content = file.read_bytes()

    with pytest.raises(ValueError) as exc:
        is_file_valid(
            filename="big.csv",
            content=content,
            allowed_extensions=[".csv"],
            allowed_mimetypes=["text/csv"],
            max_size_bytes=1000  # 1 KB limit
        )

    assert "trop volumineux" in str(exc.value).lower()
