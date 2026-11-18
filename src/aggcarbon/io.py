"""CSV input parsing and validation for aggcarbon.

The input format is one row per sample x aggregate class. Classes are fixed so
that the geometric mean diameter has a consistent, documented diameter basis.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

AGGREGATE_CLASSES: tuple[str, ...] = (">2", "1-2", "0.25-1", "<0.25")
CLASS_DIAMETER_MM: dict[str, float] = {">2": 4.0, "1-2": 1.5, "0.25-1": 0.625, "<0.25": 0.125}
COARSE_CLASSES: frozenset[str] = frozenset({">2", "1-2", "0.25-1"})

REQUIRED_COLUMNS: tuple[str, ...] = (
    "sample_id",
    "treatment",
    "block",
    "aggregate_class_mm",
    "fraction_mass_g",
    "soc_g_kg",
    "bulk_density_g_cm3",
    "depth_cm",
)
OPTIONAL_COLUMNS: tuple[str, ...] = ("poc_g_kg", "maoc_g_kg")
NUMERIC_COLUMNS: tuple[str, ...] = (
    "fraction_mass_g",
    "soc_g_kg",
    "bulk_density_g_cm3",
    "depth_cm",
    "poc_g_kg",
    "maoc_g_kg",
)
BD_MIN, BD_MAX = 0.5, 2.0
SOC_MIN, SOC_MAX = 0.0, 200.0

TEMPLATE_COMMENT = (
    "# aggcarbon input template -- SYNTHETIC example rows, replace with measured data.\n"
    "# fraction_mass_g: oven-dry mass retained on each sieve (g, sum across classes);\n"
    "# soc_g_kg / poc_g_kg / maoc_g_kg: C concentration (g C per kg soil);\n"
    "# bulk_density_g_cm3: layer bulk density; depth_cm: sampled layer thickness.\n"
    "# Fixed classes: >2, 1-2, 0.25-1, <0.25 (mm). poc_g_kg/maoc_g_kg may be blank.\n"
)


class ValidationError(ValueError):
    """Raised when the input table violates the documented schema or ranges."""

    def __init__(self, messages: list[str]) -> None:
        self.messages = tuple(messages)
        super().__init__("\n".join(self.messages))


@dataclass(frozen=True)
class AggregateRow:
    """One aggregate class of one sample."""

    aggregate_class: str
    fraction_mass_g: float
    soc_g_kg: float
    bulk_density_g_cm3: float
    depth_cm: float
    poc_g_kg: float | None
    maoc_g_kg: float | None


@dataclass(frozen=True)
class Sample:
    """A complete sample with all four aggregate classes."""

    sample_id: str
    treatment: str
    block: str
    rows: tuple[AggregateRow, ...]

    @property
    def total_mass_g(self) -> float:
        return sum(row.fraction_mass_g for row in self.rows)

    @property
    def bulk_density_g_cm3(self) -> float:
        return self.rows[0].bulk_density_g_cm3

    @property
    def depth_cm(self) -> float:
        return self.rows[0].depth_cm


@dataclass(frozen=True)
class Dataset:
    samples: tuple[Sample, ...]

    @property
    def treatments(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for sample in self.samples:
            seen.setdefault(sample.treatment, None)
        return tuple(seen)

    @property
    def n_blocks(self) -> int:
        return len({(s.treatment, s.block) for s in self.samples})


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_float(value: object, column: str, row_number: int, errors: list[str]) -> float | None:
    text = _text(value)
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        errors.append(f"row {row_number}: column {column!r} is not numeric ({text!r})")
        return None
    if number != number:  # NaN
        errors.append(f"row {row_number}: column {column!r} is NaN")
        return None
    return number


def read_dataset(path: str | Path) -> Dataset:
    """Read and validate a CSV file. Raises ValidationError on any problem."""

    csv_path = Path(path)
    if not csv_path.is_file():
        raise ValidationError([f"input file not found: {csv_path}"])

    try:
        frame = pd.read_csv(
            csv_path, comment="#", dtype=str, keep_default_na=False, encoding="utf-8-sig"
        )
    except pd.errors.EmptyDataError as exc:
        raise ValidationError(["input file is empty"]) from exc
    except pd.errors.ParserError as exc:
        raise ValidationError([f"could not parse CSV: {exc}"]) from exc
    except UnicodeDecodeError as exc:
        raise ValidationError(
            ["input is not UTF-8; re-save the CSV as UTF-8 (Excel: 另存为 → CSV UTF-8)"]
        ) from exc

    frame.columns = [str(column).strip() for column in frame.columns]
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValidationError([f"missing required column(s): {', '.join(missing)}"])
    frame = frame.apply(lambda column: column.map(_text))
    if frame.empty:
        raise ValidationError(["input file has a header but no data rows"])

    errors: list[str] = []
    grouped: dict[str, list[dict[str, object]]] = {}
    sample_identity: dict[str, tuple[str, str]] = {}

    for position, record in enumerate(frame.to_dict(orient="records"), start=2):
        sample_id = _text(record.get("sample_id"))
        treatment = _text(record.get("treatment"))
        block = _text(record.get("block"))
        aggregate_class = _text(record.get("aggregate_class_mm"))
        if not sample_id:
            errors.append(f"row {position}: sample_id is empty")
            continue
        if not treatment:
            errors.append(f"row {position}: treatment is empty")
        if not block:
            errors.append(f"row {position}: block is empty")
        if aggregate_class not in CLASS_DIAMETER_MM:
            errors.append(
                f"row {position}: unknown aggregate_class_mm {aggregate_class!r}; "
                f"expected one of {', '.join(AGGREGATE_CLASSES)}"
            )
            continue
        identity = (treatment, block)
        if sample_id in sample_identity and sample_identity[sample_id] != identity:
            errors.append(
                f"row {position}: sample_id {sample_id!r} has inconsistent treatment/block"
            )
        sample_identity.setdefault(sample_id, identity)

        values: dict[str, float | None] = {}
        for column in NUMERIC_COLUMNS:
            if column not in frame.columns:
                values[column] = None
                continue
            values[column] = _parse_float(record.get(column), column, position, errors)

        mass = values["fraction_mass_g"]
        soc = values["soc_g_kg"]
        bd = values["bulk_density_g_cm3"]
        depth = values["depth_cm"]
        poc = values["poc_g_kg"]
        maoc = values["maoc_g_kg"]

        if mass is None:
            errors.append(f"row {position}: fraction_mass_g is required")
        elif mass < 0:
            errors.append(f"row {position}: fraction_mass_g must be >= 0 (got {mass})")
        if soc is None:
            errors.append(f"row {position}: soc_g_kg is required")
        elif not SOC_MIN <= soc <= SOC_MAX:
            errors.append(f"row {position}: soc_g_kg must be within 0-200 g/kg (got {soc})")
        if bd is None:
            errors.append(f"row {position}: bulk_density_g_cm3 is required")
        elif not BD_MIN <= bd <= BD_MAX:
            errors.append(
                f"row {position}: bulk_density_g_cm3 must be within 0.5-2.0 (got {bd})"
            )
        if depth is None:
            errors.append(f"row {position}: depth_cm is required")
        elif depth <= 0:
            errors.append(f"row {position}: depth_cm must be > 0 (got {depth})")
        for name, value in (("poc_g_kg", poc), ("maoc_g_kg", maoc)):
            if value is not None and value < 0:
                errors.append(f"row {position}: {name} must be >= 0 (got {value})")

        grouped.setdefault(sample_id, []).append(
            {
                "position": position,
                "treatment": treatment,
                "block": block,
                "aggregate_class": aggregate_class,
                "mass": mass,
                "soc": soc,
                "bd": bd,
                "depth": depth,
                "poc": poc,
                "maoc": maoc,
            }
        )

    if errors:
        raise ValidationError(errors)

    samples: list[Sample] = []
    for sample_id, records in grouped.items():
        classes = [str(record["aggregate_class"]) for record in records]
        duplicates = sorted({name for name in classes if classes.count(name) > 1})
        if duplicates:
            errors.append(f"sample {sample_id!r}: duplicate aggregate class(es) {duplicates}")
        absent = [name for name in AGGREGATE_CLASSES if name not in classes]
        if absent:
            errors.append(f"sample {sample_id!r}: missing aggregate class(es) {absent}")
        if errors:
            continue
        records.sort(key=lambda record: AGGREGATE_CLASSES.index(str(record["aggregate_class"])))
        total = sum(float(record["mass"]) for record in records)
        if total <= 0:
            errors.append(f"sample {sample_id!r}: fraction masses sum to zero")
            continue
        bds = {round(float(record["bd"]), 9) for record in records}
        depths = {round(float(record["depth"]), 9) for record in records}
        if len(bds) > 1:
            errors.append(f"sample {sample_id!r}: bulk_density_g_cm3 differs between classes")
        if len(depths) > 1:
            errors.append(f"sample {sample_id!r}: depth_cm differs between classes")
        if len(bds) > 1 or len(depths) > 1:
            continue
        samples.append(
            Sample(
                sample_id=sample_id,
                treatment=str(records[0]["treatment"]),
                block=str(records[0]["block"]),
                rows=tuple(
                    AggregateRow(
                        aggregate_class=str(record["aggregate_class"]),
                        fraction_mass_g=float(record["mass"]),  # type: ignore[arg-type]
                        soc_g_kg=float(record["soc"]),  # type: ignore[arg-type]
                        bulk_density_g_cm3=float(record["bd"]),  # type: ignore[arg-type]
                        depth_cm=float(record["depth"]),  # type: ignore[arg-type]
                        poc_g_kg=None if record["poc"] is None else float(record["poc"]),  # type: ignore[arg-type]
                        maoc_g_kg=None if record["maoc"] is None else float(record["maoc"]),  # type: ignore[arg-type]
                    )
                    for record in records
                ),
            )
        )

    if errors:
        raise ValidationError(errors)
    if not samples:
        raise ValidationError(["no complete samples found"])
    return Dataset(samples=tuple(samples))


def validate_dataset(dataset: Dataset, reference: str | None = None) -> list[str]:
    """Return semantic warnings for an already parsed dataset."""

    warnings: list[str] = []
    if reference is not None:
        if not reference.strip():
            raise ValidationError(["reference treatment is empty"])
        if reference not in dataset.treatments:
            raise ValidationError(
                [f"reference treatment {reference!r} not found; available: {', '.join(dataset.treatments)}"]
            )
        if len(dataset.treatments) < 2:
            warnings.append("only one treatment present; CPI/CMI will be defined against itself")
    per_treatment: dict[str, set[str]] = {}
    for sample in dataset.samples:
        per_treatment.setdefault(sample.treatment, set()).add(sample.block)
    for treatment, blocks in per_treatment.items():
        if len(blocks) < 2:
            warnings.append(
                f"treatment {treatment!r} has {len(blocks)} block(s); bootstrap CI will be degenerate"
            )
    return warnings


def write_template(path: str | Path) -> None:
    """Write a commented template with one synthetic sample."""

    header = (
        "sample_id,treatment,block,aggregate_class_mm,fraction_mass_g,soc_g_kg,"
        "bulk_density_g_cm3,depth_cm,poc_g_kg,maoc_g_kg\n"
    )
    rows = [
        "P01,CK,1,>2,12.4,18.2,1.21,20,2.1,16.1\n",
        "P01,CK,1,1-2,18.7,16.9,1.21,20,2.0,14.9\n",
        "P01,CK,1,0.25-1,31.5,15.3,1.21,20,1.8,13.5\n",
        "P01,CK,1,<0.25,37.4,14.1,1.21,20,1.5,12.6\n",
    ]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(TEMPLATE_COMMENT + header + "".join(rows), encoding="utf-8")
