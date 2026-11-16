"""End-to-end CLI, output schema, report, and figure tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from support import write_csv

from aggcarbon.compute import SUMMARY_COLUMNS


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "aggcarbon", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def _compute(tmp_path: Path) -> tuple[Path, Path]:
    source = write_csv(tmp_path / "in.csv")
    output = tmp_path / "out"
    completed = _run(
        "compute",
        str(source),
        "--reference",
        "CK",
        "-o",
        str(output),
        "--bootstrap",
        "100",
        "--data-note",
        "合成演示数据（测试）",
        "--quiet",
    )
    assert completed.returncode == 0, completed.stderr
    return source, output


def test_cli_help_exits_zero() -> None:
    completed = _run("--help")
    assert completed.returncode == 0
    assert "compute" in completed.stdout


def test_cli_version_exits_zero() -> None:
    completed = _run("--version")
    assert completed.returncode == 0
    assert "0.1.0" in completed.stdout


def test_cli_template_writes_header(tmp_path: Path) -> None:
    target = tmp_path / "template.csv"
    completed = _run("template", "-o", str(target))
    assert completed.returncode == 0
    assert "SYNTHETIC" in target.read_text(encoding="utf-8")


def test_cli_validate_valid(tmp_path: Path) -> None:
    source = write_csv(tmp_path / "in.csv")
    completed = _run("validate", str(source))
    assert completed.returncode == 0
    assert "OK: 4 samples" in completed.stdout


def test_cli_validate_bad_exits_two(tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("bad,header\n1,2\n", encoding="utf-8")
    completed = _run("validate", str(source))
    assert completed.returncode == 2
    assert "validation failed" in completed.stderr


def test_cli_compute_missing_reference_exits_two(tmp_path: Path) -> None:
    source = write_csv(tmp_path / "in.csv")
    completed = _run("compute", str(source), "--reference", "NOPE", "-o", str(tmp_path / "out"))
    assert completed.returncode == 2
    assert "not found" in completed.stderr


def test_compute_creates_all_outputs(tmp_path: Path) -> None:
    _, output = _compute(tmp_path)
    for name in (
        "summary.csv",
        "stocks_by_class.csv",
        "result.json",
        "report.md",
        "aggregate-stability.png",
        "carbon-indices.png",
    ):
        assert (output / name).is_file(), name
    for name in ("aggregate-stability.png", "carbon-indices.png"):
        assert (output / name).stat().st_size > 10_000


def test_summary_has_every_documented_column(tmp_path: Path) -> None:
    _, output = _compute(tmp_path)
    frame = pd.read_csv(output / "summary.csv")
    assert tuple(frame.columns) == SUMMARY_COLUMNS
    assert list(frame["treatment"]) == ["CK", "M"]
    assert frame.loc[0, "CPI_mean"] == pytest.approx(100.0)
    assert frame.loc[0, "CMI_mean"] == pytest.approx(100.0)


def test_result_json_reference_and_ratio(tmp_path: Path) -> None:
    _, output = _compute(tmp_path)
    payload = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert payload["reference_treatment"] == "CK"
    reference = payload["treatments"][0]
    treatment = payload["treatments"][1]
    assert reference["metrics"]["cpi"]["mean"] == 100.0
    assert treatment["metrics"]["cpi"]["mean"] == pytest.approx(1.5)
    assert treatment["metrics"]["cmi"]["mean"] == pytest.approx(225.0)
    assert payload["data_note"] == "合成演示数据（测试）"
    assert payload["units"]["soc_stock"] == "Mg/ha"


def test_report_is_chinese_and_has_units(tmp_path: Path) -> None:
    source, output = _compute(tmp_path)
    report = (output / "report.md").read_text(encoding="utf-8")
    assert "土壤团聚体稳定性与碳库指标计算报告" in report
    assert "CMI = CPI" in report
    assert "Mg/ha" in report
    assert "假设与局限" in report
    assert "合成演示数据（测试）" in report
    assert source.name in report


def test_stocks_file_covers_every_class(tmp_path: Path) -> None:
    _, output = _compute(tmp_path)
    frame = pd.read_csv(output / "stocks_by_class.csv")
    assert len(frame) == 16
    assert set(frame["aggregate_class_mm"]) == {">2", "1-2", "0.25-1", "<0.25"}
    assert (frame["esm_factor"] == 1.0).all()


def test_compute_with_esm_scales_stocks(tmp_path: Path) -> None:
    source = write_csv(tmp_path / "in.csv")
    output = tmp_path / "out"
    completed = _run(
        "compute",
        str(source),
        "--reference",
        "CK",
        "-o",
        str(output),
        "--bootstrap",
        "50",
        "--reference-mass",
        "2000",
        "--quiet",
    )
    assert completed.returncode == 0, completed.stderr
    report = (output / "report.md").read_text(encoding="utf-8")
    assert "ESM" in report
    frame = pd.read_csv(output / "stocks_by_class.csv")
    assert np.allclose(frame["esm_factor"], 2000.0 / 2500.0)


def test_compute_prints_table(tmp_path: Path) -> None:
    source = write_csv(tmp_path / "in.csv")
    completed = _run(
        "compute", str(source), "--reference", "CK", "-o", str(tmp_path / "out"), "--bootstrap", "50"
    )
    assert completed.returncode == 0
    assert "MWD(mm)" in completed.stdout
    assert "CMI" in completed.stdout
