"""Input parsing, validation, and template tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from support import HEADER, write_csv

from aggcarbon.io import (
    AGGREGATE_CLASSES,
    ValidationError,
    read_dataset,
    validate_dataset,
    write_template,
)


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for block in (1, 2):
        for treatment, soc, poc in (("CK", 20.0, 2.0), ("M", 30.0, 3.0)):
            for name, mass in zip(AGGREGATE_CLASSES, (10.0, 10.0, 30.0, 50.0), strict=True):
                rows.append(
                    {
                        "sample_id": f"{treatment}{block}",
                        "treatment": treatment,
                        "block": block,
                        "aggregate_class_mm": name,
                        "fraction_mass_g": mass,
                        "soc_g_kg": soc,
                        "bulk_density_g_cm3": 1.25,
                        "depth_cm": 20,
                        "poc_g_kg": poc,
                        "maoc_g_kg": soc - poc,
                    }
                )
    return rows


def _write(path: Path, rows: list[dict[str, object]] | None = None) -> Path:
    return write_csv(path, _rows() if rows is None else rows)


def test_reads_valid_file(tmp_path: Path) -> None:
    dataset = read_dataset(_write(tmp_path / "in.csv"))
    assert len(dataset.samples) == 4
    assert dataset.treatments == ("CK", "M")
    assert {sample.block for sample in dataset.samples} == {"1", "2"}


def test_comments_and_blank_race_lines_are_skipped(tmp_path: Path) -> None:
    path = _write(tmp_path / "in.csv")
    path.write_text("# synthetic note\n\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    dataset = read_dataset(path)
    assert len(dataset.samples) == 4


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="not found"):
        read_dataset(tmp_path / "absent.csv")


def test_empty_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValidationError, match="empty"):
        read_dataset(path)


def test_missing_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "in.csv"
    path.write_text("sample_id,treatment,block,aggregate_class_mm\nA,CK,1,>2\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="missing required column"):
        read_dataset(path)


def test_unknown_class_raises(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["aggregate_class_mm"] = "5-10"
    with pytest.raises(ValidationError, match="unknown aggregate_class"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_missing_class_raises(tmp_path: Path) -> None:
    rows = [row for row in _rows() if not (row["sample_id"] == "CK1" and row["aggregate_class_mm"] == "<0.25")]
    with pytest.raises(ValidationError, match="missing aggregate class"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_duplicate_class_raises(tmp_path: Path) -> None:
    rows = _rows() + [_rows()[0]]
    with pytest.raises(ValidationError, match="duplicate aggregate class"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_negative_mass_raises(tmp_path: Path) -> None:
    rows = _rows()
    rows[1]["fraction_mass_g"] = -1.0
    with pytest.raises(ValidationError, match="fraction_mass_g must be >= 0"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_zero_total_mass_raises(tmp_path: Path) -> None:
    rows = _rows()
    for row in rows[:4]:
        row["fraction_mass_g"] = 0.0
    with pytest.raises(ValidationError, match="sum to zero"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_bulk_density_out_of_range_raises(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["bulk_density_g_cm3"] = 0.4
    with pytest.raises(ValidationError, match="bulk_density_g_cm3 must be within 0.5-2.0"):
        read_dataset(_write(tmp_path / "in.csv", rows))
    rows[0]["bulk_density_g_cm3"] = 2.1
    with pytest.raises(ValidationError, match="bulk_density_g_cm3 must be within 0.5-2.0"):
        read_dataset(_write(tmp_path / "in2.csv", rows))


def test_soc_out_of_range_raises(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["soc_g_kg"] = 250.0
    with pytest.raises(ValidationError, match="soc_g_kg must be within 0-200"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_non_positive_depth_raises(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["depth_cm"] = 0.0
    with pytest.raises(ValidationError, match="depth_cm must be > 0"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_negative_poc_raises(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["poc_g_kg"] = -0.5
    with pytest.raises(ValidationError, match="poc_g_kg must be >= 0"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_non_numeric_value_raises(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["soc_g_kg"] = "high"
    with pytest.raises(ValidationError, match="not numeric"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_empty_treatment_raises(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["treatment"] = ""
    with pytest.raises(ValidationError, match="treatment is empty"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_inconsistent_sample_identity_raises(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["treatment"] = "M"
    with pytest.raises(ValidationError, match="inconsistent treatment/block"):
        read_dataset(_write(tmp_path / "in.csv", rows))


def test_multiple_errors_are_collected(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["soc_g_kg"] = -1
    rows[1]["bulk_density_g_cm3"] = 9
    with pytest.raises(ValidationError) as caught:
        read_dataset(_write(tmp_path / "in.csv", rows))
    assert len(caught.value.messages) >= 2


def test_header_only_raises(tmp_path: Path) -> None:
    path = tmp_path / "in.csv"
    path.write_text(HEADER + "\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="no data rows"):
        read_dataset(path)


def test_template_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "template.csv"
    write_template(path)
    text = path.read_text(encoding="utf-8")
    assert "SYNTHETIC" in text
    dataset = read_dataset(path)
    assert len(dataset.samples) == 1
    assert dataset.samples[0].treatment == "CK"
    assert len(dataset.samples[0].rows) == 4


def test_validate_dataset_reference_and_warnings() -> None:
    from support import make_dataset

    dataset = make_dataset()
    assert validate_dataset(dataset, "CK") == []
    with pytest.raises(ValidationError, match="not found"):
        validate_dataset(dataset, "NOPE")
    with pytest.raises(ValidationError, match="empty"):
        validate_dataset(dataset, " ")


def test_validate_dataset_single_block_warning() -> None:
    from support import make_sample

    from aggcarbon.io import Dataset

    dataset = Dataset(samples=(make_sample("A"),))
    warnings = validate_dataset(dataset)
    assert any("degenerate" in warning for warning in warnings)
