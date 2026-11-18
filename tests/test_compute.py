"""Numerical checks against independently hand-calculated fixtures."""

from __future__ import annotations

import math

import numpy as np
import pytest
from support import make_dataset, make_sample

from aggcarbon.compute import compute_dataset, compute_sample
from aggcarbon.io import Dataset, ValidationError


def _two_class_sample() -> object:
    return make_sample("P01", masses=(70.0, 30.0), soc=10.0, bd=1.5, depth=20.0)


def test_mwd_hand_calculation() -> None:
    metrics = compute_sample(_two_class_sample())
    assert metrics.mwd == pytest.approx(2.8375)
    assert metrics.proportions[">2"] == pytest.approx(0.7)
    assert metrics.proportions["<0.25"] == pytest.approx(0.3)
    assert sum(metrics.proportions.values()) == pytest.approx(1.0)


def test_gmd_hand_calculation() -> None:
    metrics = compute_sample(_two_class_sample())
    expected = math.exp(0.7 * math.log(4.0) + 0.3 * math.log(0.125))
    assert metrics.gmd == pytest.approx(expected, rel=1e-12)


def test_r025_hand_calculation() -> None:
    metrics = compute_sample(_two_class_sample())
    assert metrics.r025 == pytest.approx(0.7)


def test_stock_hand_calculation() -> None:
    sample = make_sample("P01", masses=(100.0, 0.0, 0.0, 0.0), soc=10.0, bd=1.5, depth=20.0)
    metrics = compute_sample(sample)
    assert metrics.soil_mass_mg_ha == pytest.approx(3000.0)
    assert metrics.soc_stock == pytest.approx(30.0)


def test_esm_scales_stocks_by_reference_mass() -> None:
    sample = make_sample("P01", masses=(100.0, 0.0, 0.0, 0.0), soc=10.0, bd=1.5, depth=20.0)
    plain = compute_sample(sample)
    corrected = compute_sample(sample, reference_mass_mg_ha=2000.0)
    assert corrected.esm_factor == pytest.approx(2000.0 / 3000.0)
    assert corrected.soc_stock == pytest.approx(plain.soc_stock * 2000.0 / 3000.0)
    assert corrected.poc_stock == pytest.approx(plain.poc_stock * 2000.0 / 3000.0)


def test_esm_leaves_ratio_unchanged() -> None:
    sample = make_sample("P01", masses=(20.0, 20.0, 30.0, 30.0), soc=20.0, poc=4.0, maoc=16.0)
    plain = compute_sample(sample)
    corrected = compute_sample(sample, reference_mass_mg_ha=2400.0)
    assert plain.poc_maoc_ratio == pytest.approx(0.25)
    assert corrected.poc_maoc_ratio == pytest.approx(plain.poc_maoc_ratio)


def test_li_hand_calculation() -> None:
    sample = make_sample("P01", masses=(100.0, 0.0, 0.0, 0.0), soc=10.0, poc=4.0, maoc=6.0)
    metrics = compute_sample(sample)
    assert metrics.soc_stock == pytest.approx(25.0)
    assert metrics.poc_stock == pytest.approx(10.0)
    assert metrics.li == pytest.approx(0.4)


def test_li_is_unchanged_by_esm() -> None:
    sample = make_sample("P01", masses=(100.0, 0.0, 0.0, 0.0), soc=10.0, poc=4.0, maoc=6.0)
    plain = compute_sample(sample)
    corrected = compute_sample(sample, reference_mass_mg_ha=1500.0)
    assert corrected.li == pytest.approx(plain.li)


def test_li_is_nan_when_poc_missing() -> None:
    sample = make_sample("P01", masses=(100.0, 0.0, 0.0, 0.0), soc=10.0, poc=None)
    metrics = compute_sample(sample)
    assert math.isnan(metrics.li)


def test_zero_mass_class_is_ignored_by_gmd() -> None:
    sample = make_sample("P01", masses=(50.0, 0.0, 0.0, 50.0), soc=10.0)
    metrics = compute_sample(sample)
    assert metrics.gmd == pytest.approx(math.sqrt(0.5))
    assert metrics.mwd == pytest.approx(2.0625)


def test_cpi_and_cmi_definition() -> None:
    result = compute_dataset(make_dataset(), reference="CK", bootstrap=200)
    summary = {item.treatment: item for item in result.summaries}
    assert summary["M"].stats["cpi"].mean == pytest.approx(1.5)
    assert summary["M"].stats["cmi"].mean == pytest.approx(225.0)


def test_reference_cpi_is_one_and_cmi_is_100() -> None:
    result = compute_dataset(make_dataset(), reference="CK", bootstrap=200)
    reference = result.summaries[0]
    assert reference.treatment == "CK"
    assert reference.stats["cpi"].mean == 1.0
    assert reference.stats["cmi"].mean == 100.0
    assert reference.stats["cpi"].ci_low == 1.0
    assert reference.stats["cmi"].ci_high == 100.0


def test_reference_is_listed_first_then_input_order() -> None:
    dataset = make_dataset()
    result = compute_dataset(dataset, reference="M", bootstrap=100)
    assert [item.treatment for item in result.summaries] == ["M", "CK"]
    ck = result.summaries[1]
    assert ck.stats["cpi"].mean == pytest.approx(2.0 / 3.0)
    assert ck.stats["cmi"].mean == pytest.approx((2.0 / 3.0) * (20.0 / 30.0) * 100.0)


def test_bootstrap_is_reproducible_with_seed() -> None:
    first = compute_dataset(make_dataset(), reference="CK", bootstrap=300, seed=7)
    second = compute_dataset(make_dataset(), reference="CK", bootstrap=300, seed=7)
    for left, right in zip(first.summaries, second.summaries, strict=True):
        assert left.stats["cmi"].ci_low == pytest.approx(right.stats["cmi"].ci_low)
        assert left.stats["cmi"].ci_high == pytest.approx(right.stats["cmi"].ci_high)


def test_bootstrap_changes_with_seed() -> None:
    first = compute_dataset(make_dataset(), reference="CK", bootstrap=300, seed=1)
    second = compute_dataset(make_dataset(), reference="CK", bootstrap=300, seed=2)
    cmi_a = first.summaries[1].stats["cmi"]
    cmi_b = second.summaries[1].stats["cmi"]
    assert (cmi_a.ci_low, cmi_a.ci_high) != pytest.approx((cmi_b.ci_low, cmi_b.ci_high))


def test_confidence_interval_brackets_mean() -> None:
    result = compute_dataset(make_dataset(), reference="CK", bootstrap=300)
    for summary in result.summaries:
        for metric in ("mwd", "gmd", "soc_stock", "cmi"):
            stat = summary.stats[metric]
            assert stat.ci_low <= stat.mean + 1e-9
            assert stat.ci_high >= stat.mean - 1e-9


def test_class_stocks_sum_to_sample_stock() -> None:
    result = compute_dataset(make_dataset(), reference="CK", bootstrap=100)
    total = sum(item.stock_mg_ha for item in result.class_stocks if item.sample_id == "CK1")
    sample = next(item for item in result.samples if item.sample_id == "CK1")
    assert total == pytest.approx(sample.soc_stock)
    assert len(result.class_stocks) == 4 * len(result.samples)


def test_esm_applies_to_class_stocks() -> None:
    plain = compute_dataset(make_dataset(), reference="CK", bootstrap=100)
    corrected = compute_dataset(make_dataset(), reference="CK", bootstrap=100, reference_mass_mg_ha=2400.0)
    plain_total = sum(item.stock_mg_ha for item in plain.class_stocks)
    corrected_total = sum(item.stock_mg_ha for item in corrected.class_stocks)
    assert corrected.class_stocks[0].esm_factor != pytest.approx(1.0)
    assert corrected_total == pytest.approx(plain_total * 2400.0 / 2500.0)


def test_missing_poc_gives_nan_cpi() -> None:
    dataset = Dataset(
        samples=(
            make_sample("CK1", treatment="CK", block="1", poc=None),
            make_sample("M1", treatment="M", block="1", poc=None),
        )
    )
    result = compute_dataset(dataset, reference="CK", bootstrap=50)
    assert result.summaries[0].stats["cpi"].mean == 1.0
    assert np.isnan(result.summaries[1].stats["cpi"].mean)
    assert np.isnan(result.summaries[1].stats["cmi"].mean)


def test_single_block_emits_warning() -> None:
    dataset = Dataset(
        samples=(
            make_sample("CK1", treatment="CK", block="1"),
            make_sample("M1", treatment="M", block="1"),
        )
    )
    result = compute_dataset(dataset, reference="CK", bootstrap=50)
    assert any("degenerate" in warning for warning in result.warnings)


def test_empty_reference_raises() -> None:
    with pytest.raises(ValidationError, match="empty"):
        compute_dataset(make_dataset(), reference="  ")


def test_unknown_reference_raises() -> None:
    with pytest.raises(ValidationError, match="not found"):
        compute_dataset(make_dataset(), reference="NOPE")


def test_invalid_bootstrap_raises() -> None:
    with pytest.raises(ValidationError, match="bootstrap"):
        compute_dataset(make_dataset(), reference="CK", bootstrap=5)


def test_invalid_confidence_raises() -> None:
    with pytest.raises(ValidationError, match="confidence"):
        compute_dataset(make_dataset(), reference="CK", confidence=1.2)


def test_invalid_reference_mass_raises() -> None:
    with pytest.raises(ValidationError, match="reference mass"):
        compute_dataset(make_dataset(), reference="CK", reference_mass_mg_ha=0)
