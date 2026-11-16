"""Shared builders for the test suite."""

from __future__ import annotations

from pathlib import Path

from aggcarbon.io import AGGREGATE_CLASSES, AggregateRow, Dataset, Sample

HEADER = (
    "sample_id,treatment,block,aggregate_class_mm,fraction_mass_g,soc_g_kg,"
    "bulk_density_g_cm3,depth_cm,poc_g_kg,maoc_g_kg"
)


def make_sample(
    sample_id: str,
    treatment: str = "CK",
    block: str = "1",
    masses: tuple[float, ...] = (20.0, 20.0, 30.0, 30.0),
    soc: float = 20.0,
    bd: float = 1.25,
    depth: float = 20.0,
    poc: float | None = 2.0,
    maoc: float | None = None,
) -> Sample:
    if len(masses) == 4:
        classes = AGGREGATE_CLASSES
    elif len(masses) == 2:
        classes = (AGGREGATE_CLASSES[0], AGGREGATE_CLASSES[-1])
    else:
        classes = AGGREGATE_CLASSES[: len(masses)]
    rows = []
    for name, mass in zip(classes, masses, strict=True):
        if poc is None:
            maoc_value = None
        else:
            maoc_value = soc - poc if maoc is None else maoc
        rows.append(
            AggregateRow(
                aggregate_class=name,
                fraction_mass_g=mass,
                soc_g_kg=soc,
                bulk_density_g_cm3=bd,
                depth_cm=depth,
                poc_g_kg=poc,
                maoc_g_kg=maoc_value,
            )
        )
    return Sample(sample_id=sample_id, treatment=treatment, block=block, rows=tuple(rows))


def make_dataset(
    masses_ck: tuple[float, ...] = (10.0, 10.0, 30.0, 50.0),
    masses_m: tuple[float, ...] = (30.0, 20.0, 30.0, 20.0),
) -> Dataset:
    samples = []
    # Symmetric block offsets keep treatment means at SOC 20/30 and POC 2/3
    # while giving the block bootstrap something to resample.
    offsets = {1: -0.4, 2: 0.0, 3: 0.4}
    for block in (1, 2, 3):
        shift = offsets[block]
        samples.append(
            make_sample(
                f"CK{block}",
                treatment="CK",
                block=str(block),
                masses=masses_ck,
                soc=20.0 + shift,
                poc=2.0 + shift / 4.0,
            )
        )
        samples.append(
            make_sample(
                f"M{block}",
                treatment="M",
                block=str(block),
                masses=masses_m,
                soc=30.0 + shift,
                poc=3.0 + shift / 4.0,
            )
        )
    return Dataset(samples=tuple(samples))


def write_csv(path: Path, rows: list[dict[str, object]] | None = None) -> Path:
    if rows is None:
        rows = []
        for block in (1, 2):
            for treatment, soc, masses in (
                ("CK", 20.0, (10.0, 10.0, 30.0, 50.0)),
                ("M", 30.0, (30.0, 20.0, 30.0, 20.0)),
            ):
                for name, mass in zip(AGGREGATE_CLASSES, masses, strict=True):
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
                            "poc_g_kg": 2.0 if treatment == "CK" else 3.0,
                            "maoc_g_kg": soc - (2.0 if treatment == "CK" else 3.0),
                        }
                    )
    lines = [HEADER]
    for row in rows:
        lines.append(",".join(str(row[column]) for column in HEADER.split(",")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
