"""Core calculations for aggregate stability and soil carbon pool indices.

All formulas follow ``docs/methods.md``. Units are kept explicit in names:
masses in g, concentrations in g/kg, bulk density in g/cm3, depth in cm,
carbon stocks in Mg/ha, and diameters in mm.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from aggcarbon.io import (
    CLASS_DIAMETER_MM,
    COARSE_CLASSES,
    Dataset,
    Sample,
    ValidationError,
    validate_dataset,
)

METRICS: tuple[str, ...] = (
    "mwd",
    "gmd",
    "r025",
    "soc_stock",
    "poc_stock",
    "maoc_stock",
    "poc_maoc_ratio",
)

METRIC_UNITS: dict[str, str] = {
    "mwd": "mm",
    "gmd": "mm",
    "r025": "fraction (0-1)",
    "soc_stock": "Mg/ha",
    "poc_stock": "Mg/ha",
    "maoc_stock": "Mg/ha",
    "poc_maoc_ratio": "g/g",
}

SUMMARY_COLUMNS: tuple[str, ...] = (
    "treatment",
    "n_samples",
    "n_blocks",
    "MWD_mm_mean",
    "MWD_mm_sd",
    "MWD_mm_ci_low",
    "MWD_mm_ci_high",
    "GMD_mm_mean",
    "GMD_mm_sd",
    "GMD_mm_ci_low",
    "GMD_mm_ci_high",
    "R_gt_0.25_mean",
    "R_gt_0.25_sd",
    "R_gt_0.25_ci_low",
    "R_gt_0.25_ci_high",
    "SOC_stock_Mg_ha_mean",
    "SOC_stock_Mg_ha_sd",
    "SOC_stock_Mg_ha_ci_low",
    "SOC_stock_Mg_ha_ci_high",
    "POC_stock_Mg_ha_mean",
    "POC_stock_Mg_ha_sd",
    "POC_stock_Mg_ha_ci_low",
    "POC_stock_Mg_ha_ci_high",
    "MAOC_stock_Mg_ha_mean",
    "MAOC_stock_Mg_ha_sd",
    "MAOC_stock_Mg_ha_ci_low",
    "MAOC_stock_Mg_ha_ci_high",
    "POC_MAOC_ratio_mean",
    "POC_MAOC_ratio_sd",
    "POC_MAOC_ratio_ci_low",
    "POC_MAOC_ratio_ci_high",
    "CPI_mean",
    "CPI_sd",
    "CPI_ci_low",
    "CPI_ci_high",
    "CMI_mean",
    "CMI_sd",
    "CMI_ci_low",
    "CMI_ci_high",
)

_CSV_METRIC_NAMES: dict[str, str] = {
    "mwd": "MWD_mm",
    "gmd": "GMD_mm",
    "r025": "R_gt_0.25",
    "soc_stock": "SOC_stock_Mg_ha",
    "poc_stock": "POC_stock_Mg_ha",
    "maoc_stock": "MAOC_stock_Mg_ha",
    "poc_maoc_ratio": "POC_MAOC_ratio",
}


@dataclass(frozen=True)
class SampleMetrics:
    sample_id: str
    treatment: str
    block: str
    proportions: dict[str, float]
    mwd: float
    gmd: float
    r025: float
    soil_mass_mg_ha: float
    esm_factor: float
    soc_stock: float
    poc_stock: float
    maoc_stock: float
    poc_maoc_ratio: float


@dataclass(frozen=True)
class Stat:
    mean: float
    sd: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class TreatmentSummary:
    treatment: str
    n_samples: int
    n_blocks: int
    stats: dict[str, Stat]

    def csv_row(self) -> dict[str, object]:
        row: dict[str, object] = {
            "treatment": self.treatment,
            "n_samples": self.n_samples,
            "n_blocks": self.n_blocks,
        }
        for metric in METRICS:
            stat = self.stats[metric]
            prefix = _CSV_METRIC_NAMES[metric]
            row[f"{prefix}_mean"] = stat.mean
            row[f"{prefix}_sd"] = stat.sd
            row[f"{prefix}_ci_low"] = stat.ci_low
            row[f"{prefix}_ci_high"] = stat.ci_high
        cpi = self.stats["cpi"]
        cmi = self.stats["cmi"]
        row.update(
            {
                "CPI_mean": cpi.mean,
                "CPI_sd": cpi.sd,
                "CPI_ci_low": cpi.ci_low,
                "CPI_ci_high": cpi.ci_high,
                "CMI_mean": cmi.mean,
                "CMI_sd": cmi.sd,
                "CMI_ci_low": cmi.ci_low,
                "CMI_ci_high": cmi.ci_high,
            }
        )
        return row


@dataclass(frozen=True)
class ClassStock:
    sample_id: str
    treatment: str
    block: str
    aggregate_class: str
    proportion: float
    soc_g_kg: float
    soil_mass_mg_ha: float
    esm_factor: float
    stock_mg_ha: float
    poc_stock_mg_ha: float
    maoc_stock_mg_ha: float


@dataclass(frozen=True)
class ComputeResult:
    reference: str
    reference_mass_mg_ha: float | None
    bootstrap: int
    seed: int
    confidence: float
    warnings: tuple[str, ...]
    summaries: tuple[TreatmentSummary, ...]
    samples: tuple[SampleMetrics, ...]
    class_stocks: tuple[ClassStock, ...]
    class_means: dict[str, dict[str, float]]

    def summary_rows(self) -> list[dict[str, object]]:
        return [summary.csv_row() for summary in self.summaries]


def _nan_mean(values: list[float]) -> float:
    array = np.asarray(values, dtype=float)
    if array.size == 0 or np.all(np.isnan(array)):
        return float("nan")
    return float(np.nanmean(array))


def compute_sample(sample: Sample, reference_mass_mg_ha: float | None = None) -> SampleMetrics:
    """Compute all sample-level indices for one complete sample."""

    total_mass = sample.total_mass_g
    proportions = {
        row.aggregate_class: row.fraction_mass_g / total_mass for row in sample.rows
    }
    mwd = sum(proportions[name] * CLASS_DIAMETER_MM[name] for name in proportions)
    gmd = float(
        np.exp(
            sum(
                proportion * np.log(CLASS_DIAMETER_MM[name])
                for name, proportion in proportions.items()
                if proportion > 0
            )
        )
    )
    r025 = sum(proportion for name, proportion in proportions.items() if name in COARSE_CLASSES)

    bulk_density = sample.bulk_density_g_cm3
    depth_cm = sample.depth_cm
    soil_mass = bulk_density * depth_cm * 100.0
    esm_factor = 1.0 if reference_mass_mg_ha is None else reference_mass_mg_ha / soil_mass

    soc_stock = 0.0
    poc_stock = 0.0
    maoc_stock = 0.0
    poc_complete = True
    maoc_complete = True
    for row in sample.rows:
        proportion = proportions[row.aggregate_class]
        soc_stock += soil_mass * proportion * row.soc_g_kg / 1000.0
        if row.poc_g_kg is None:
            poc_complete = False
        else:
            poc_stock += soil_mass * proportion * row.poc_g_kg / 1000.0
        if row.maoc_g_kg is None:
            maoc_complete = False
        else:
            maoc_stock += soil_mass * proportion * row.maoc_g_kg / 1000.0
    if not poc_complete:
        poc_stock = float("nan")
    if not maoc_complete:
        maoc_stock = float("nan")
    poc_maoc_ratio = (
        poc_stock / maoc_stock
        if np.isfinite(poc_stock) and np.isfinite(maoc_stock) and maoc_stock > 0
        else float("nan")
    )

    return SampleMetrics(
        sample_id=sample.sample_id,
        treatment=sample.treatment,
        block=sample.block,
        proportions=proportions,
        mwd=float(mwd),
        gmd=gmd,
        r025=float(r025),
        soil_mass_mg_ha=soil_mass,
        esm_factor=esm_factor,
        soc_stock=soc_stock * esm_factor,
        poc_stock=poc_stock * esm_factor,
        maoc_stock=maoc_stock * esm_factor,
        poc_maoc_ratio=poc_maoc_ratio,
    )


def _percentile_ci(values: np.ndarray, confidence: float) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan"), float("nan")
    alpha = (1.0 - confidence) / 2.0
    low, high = np.percentile(finite, [alpha * 100.0, (1.0 - alpha) * 100.0])
    return float(low), float(high)


def _bootstrap_means(
    grouped: dict[str, list[SampleMetrics]],
    rng: np.random.Generator,
    replicates: int,
) -> dict[str, dict[str, np.ndarray]]:
    """Resample blocks (with replacement) within each treatment."""

    draws: dict[str, dict[str, np.ndarray]] = {}
    for treatment, samples in grouped.items():
        blocks = sorted({sample.block for sample in samples})
        by_block: dict[str, list[SampleMetrics]] = defaultdict(list)
        for sample in samples:
            by_block[sample.block].append(sample)
        arrays = {metric: np.empty(replicates) for metric in METRICS}
        for replicate in range(replicates):
            chosen = [blocks[index] for index in rng.integers(0, len(blocks), size=len(blocks))]
            picked = [sample for block in chosen for sample in by_block[block]]
            for metric in METRICS:
                arrays[metric][replicate] = _nan_mean([getattr(s, metric) for s in picked])
        draws[treatment] = arrays
    return draws


def compute_dataset(
    dataset: Dataset,
    reference: str,
    reference_mass_mg_ha: float | None = None,
    bootstrap: int = 2000,
    seed: int = 42,
    confidence: float = 0.95,
) -> ComputeResult:
    """Run the full calculation, including bootstrap confidence intervals."""

    if not reference or not reference.strip():
        raise ValidationError(["reference treatment is empty"])
    if reference_mass_mg_ha is not None and reference_mass_mg_ha <= 0:
        raise ValidationError(["reference mass must be > 0 Mg/ha"])
    if bootstrap < 10:
        raise ValidationError(["bootstrap replicates must be >= 10"])
    if not 0.0 < confidence < 1.0:
        raise ValidationError(["confidence must be between 0 and 1"])
    warnings = list(validate_dataset(dataset, reference))

    samples = [compute_sample(sample, reference_mass_mg_ha) for sample in dataset.samples]
    for sample in samples:
        if sample.poc_stock != sample.poc_stock or sample.maoc_stock != sample.maoc_stock:
            warnings.append(
                f"sample {sample.sample_id!r}: POC/MAOC incomplete; CPI/CMI and ratios are NaN"
            )
        elif sample.poc_stock + sample.maoc_stock > sample.soc_stock * 1.05:
            warnings.append(
                f"sample {sample.sample_id!r}: POC + MAOC exceeds SOC by >5%; check units"
            )

    grouped: dict[str, list[SampleMetrics]] = defaultdict(list)
    for sample in samples:
        grouped[sample.treatment].append(sample)

    treatments = [reference] + [name for name in grouped if name != reference]
    rng = np.random.default_rng(seed)
    draws = _bootstrap_means(grouped, rng, bootstrap)
    point = {metric: {name: _nan_mean([getattr(s, metric) for s in grouped[name]]) for name in treatments} for metric in METRICS}

    for metric in METRICS:
        for name in treatments:
            if not np.isfinite(point[metric][name]):
                warnings.append(f"treatment {name!r}: metric {metric!r} is undefined (NaN)")

    cpi_draws: dict[str, np.ndarray] = {}
    cmi_draws: dict[str, np.ndarray] = {}
    ref_poc = point["poc_stock"][reference]
    ref_soc = point["soc_stock"][reference]
    for name in treatments:
        if name == reference:
            cpi_draws[name] = np.full(bootstrap, 100.0)
            cmi_draws[name] = np.full(bootstrap, 100.0)
            continue
        if not np.isfinite(ref_poc) or ref_poc == 0:
            cpi_draws[name] = np.full(bootstrap, np.nan)
        else:
            cpi_draws[name] = draws[name]["poc_stock"] / draws[reference]["poc_stock"]
        if not np.isfinite(ref_poc) or ref_poc == 0 or not np.isfinite(ref_soc) or ref_soc == 0:
            cmi_draws[name] = np.full(bootstrap, np.nan)
        else:
            cmi_draws[name] = (
                cpi_draws[name]
                * (draws[name]["soc_stock"] / draws[reference]["soc_stock"])
                * 100.0
            )

    summaries: list[TreatmentSummary] = []
    for name in treatments:
        members = grouped[name]
        stats: dict[str, Stat] = {}
        for metric in METRICS:
            values = [getattr(sample, metric) for sample in members]
            finite_values = [value for value in values if np.isfinite(value)]
            mean = point[metric][name]
            sd = float(np.std(finite_values, ddof=1)) if len(finite_values) > 1 else 0.0
            low, high = _percentile_ci(draws[name][metric], confidence)
            stats[metric] = Stat(mean=mean, sd=sd, ci_low=low, ci_high=high)

        if name == reference:
            stats["cpi"] = Stat(mean=100.0, sd=0.0, ci_low=100.0, ci_high=100.0)
            stats["cmi"] = Stat(mean=100.0, sd=0.0, ci_low=100.0, ci_high=100.0)
        else:
            cpi_mean = (
                point["poc_stock"][name] / ref_poc
                if np.isfinite(ref_poc) and ref_poc != 0
                else float("nan")
            )
            cmi_mean = (
                cpi_mean * (point["soc_stock"][name] / ref_soc) * 100.0
                if np.isfinite(ref_poc)
                and ref_poc != 0
                and np.isfinite(ref_soc)
                and ref_soc != 0
                and np.isfinite(cpi_mean)
                else float("nan")
            )
            cpi_low, cpi_high = _percentile_ci(cpi_draws[name], confidence)
            cmi_low, cmi_high = _percentile_ci(cmi_draws[name], confidence)
            cpi_sd = (
                float(np.nanstd(cpi_draws[name], ddof=1)) if np.isfinite(cpi_draws[name]).any() else float("nan")
            )
            cmi_sd = (
                float(np.nanstd(cmi_draws[name], ddof=1)) if np.isfinite(cmi_draws[name]).any() else float("nan")
            )
            stats["cpi"] = Stat(cpi_mean, cpi_sd, cpi_low, cpi_high)
            stats["cmi"] = Stat(cmi_mean, cmi_sd, cmi_low, cmi_high)

        summaries.append(
            TreatmentSummary(
                treatment=name,
                n_samples=len(members),
                n_blocks=len({sample.block for sample in members}),
                stats=stats,
            )
        )

    class_stocks: list[ClassStock] = []
    for sample in dataset.samples:
        metrics = compute_sample(sample, reference_mass_mg_ha)
        for row in sample.rows:
            proportion = metrics.proportions[row.aggregate_class]
            factor = metrics.esm_factor
            class_stocks.append(
                ClassStock(
                    sample_id=sample.sample_id,
                    treatment=sample.treatment,
                    block=sample.block,
                    aggregate_class=row.aggregate_class,
                    proportion=proportion,
                    soc_g_kg=row.soc_g_kg,
                    soil_mass_mg_ha=metrics.soil_mass_mg_ha,
                    esm_factor=factor,
                    stock_mg_ha=metrics.soil_mass_mg_ha * proportion * row.soc_g_kg / 1000.0 * factor,
                    poc_stock_mg_ha=(
                        metrics.soil_mass_mg_ha * proportion * row.poc_g_kg / 1000.0 * factor
                        if row.poc_g_kg is not None
                        else float("nan")
                    ),
                    maoc_stock_mg_ha=(
                        metrics.soil_mass_mg_ha * proportion * row.maoc_g_kg / 1000.0 * factor
                        if row.maoc_g_kg is not None
                        else float("nan")
                    ),
                )
            )

    class_means: dict[str, dict[str, float]] = {}
    for name in treatments:
        members = [sample for sample in samples if sample.treatment == name]
        class_means[name] = {
            name_class: _nan_mean([sample.proportions[name_class] for sample in members])
            for name_class in CLASS_DIAMETER_MM
        }

    unique_warnings = tuple(dict.fromkeys(warnings))
    return ComputeResult(
        reference=reference,
        reference_mass_mg_ha=reference_mass_mg_ha,
        bootstrap=bootstrap,
        seed=seed,
        confidence=confidence,
        warnings=unique_warnings,
        summaries=tuple(summaries),
        samples=tuple(samples),
        class_stocks=tuple(class_stocks),
        class_means=class_means,
    )
