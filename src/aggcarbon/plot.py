"""Matplotlib figures for aggregate distribution and carbon indices."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from aggcarbon.compute import ComputeResult  # noqa: E402
from aggcarbon.io import AGGREGATE_CLASSES  # noqa: E402

CLASS_COLORS = {
    ">2": "#1b4965",
    "1-2": "#3d7ea6",
    "0.25-1": "#8fc1d4",
    "<0.25": "#d9e4ec",
}
TREATMENT_COLORS = ("#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b3", "#937860")
REFERENCE_COLOR = "#8a8a8a"

_FONT_CANDIDATES = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC")


def configure_fonts() -> None:
    """Pick an installed CJK font so Chinese labels render on Windows and Linux."""

    installed = {entry.name for entry in font_manager.fontManager.ttflist}
    chosen = [name for name in _FONT_CANDIDATES if name in installed]
    plt.rcParams["font.sans-serif"] = chosen + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 130
    plt.rcParams["savefig.dpi"] = 180
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False


def _treatment_labels(result: ComputeResult) -> list[str]:
    return [summary.treatment for summary in result.summaries]


def plot_aggregate_stability(result: ComputeResult, path: str | Path) -> Path:
    """Stacked mean aggregate mass distribution per treatment."""

    configure_fonts()
    labels = _treatment_labels(result)
    figure, axis = plt.subplots(figsize=(7.2, 4.4))
    bottom = np.zeros(len(labels))
    x = np.arange(len(labels))
    for aggregate_class in AGGREGATE_CLASSES:
        values = np.array([result.class_means[name][aggregate_class] for name in labels]) * 100.0
        axis.bar(
            x,
            values,
            bottom=bottom,
            width=0.62,
            color=CLASS_COLORS[aggregate_class],
            edgecolor="white",
            linewidth=0.8,
            label=f"{aggregate_class} mm",
        )
        bottom += values
    axis.set_xticks(x, labels)
    axis.set_xlabel("处理 Treatment")
    axis.set_ylabel("质量比例 Mass proportion (%)")
    axis.set_ylim(0, 100)
    counts = ", ".join(f"{s.treatment} n={s.n_samples}" for s in result.summaries)
    axis.set_title(f"湿筛团聚体粒级分布（{counts}）")
    axis.legend(
        title="粒级 Aggregate class",
        frameon=False,
        ncol=4,
        fontsize=8,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.2),
    )
    figure.tight_layout()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(target, bbox_inches="tight")
    plt.close(figure)
    return target


def _panel(axis: plt.Axes, treatments: list[str], means: list[float], lows: list[float], highs: list[float], title: str, ylabel: str, reference: str) -> None:
    x = np.arange(len(treatments))
    colors = [REFERENCE_COLOR if name == reference else TREATMENT_COLORS[i % len(TREATMENT_COLORS)] for i, name in enumerate(treatments)]
    errors = np.array(
        [
            [mean - low if np.isfinite(low) else 0.0 for mean, low in zip(means, lows, strict=True)],
            [high - mean if np.isfinite(high) else 0.0 for mean, high in zip(means, highs, strict=True)],
        ]
    )
    axis.errorbar(
        x,
        means,
        yerr=errors,
        fmt="none",
        ecolor="#333333",
        elinewidth=1.1,
        capsize=4,
        capthick=1.1,
        zorder=2,
    )
    axis.scatter(x, means, s=62, c=colors, edgecolor="white", linewidth=0.8, zorder=3)
    axis.plot(x, means, color="#9a9a9a", linewidth=0.8, zorder=1)
    axis.set_xticks(x, treatments)
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    for index, mean in enumerate(means):
        if np.isfinite(mean):
            anchor = highs[index] if np.isfinite(highs[index]) else mean
            axis.annotate(
                f"{mean:.2f}",
                (index, anchor),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=8,
            )
    axis.margins(y=0.14)


def plot_carbon_indices(result: ComputeResult, path: str | Path) -> Path:
    """MWD, GMD and CMI per treatment with bootstrap 95% error bars."""

    configure_fonts()
    labels = _treatment_labels(result)
    by_name = {summary.treatment: summary for summary in result.summaries}
    figure, axes = plt.subplots(1, 3, figsize=(10.6, 4.2))

    _panel(
        axes[0],
        labels,
        [by_name[name].stats["mwd"].mean for name in labels],
        [by_name[name].stats["mwd"].ci_low for name in labels],
        [by_name[name].stats["mwd"].ci_high for name in labels],
        "平均重量直径 MWD",
        "MWD (mm)",
        result.reference,
    )
    _panel(
        axes[1],
        labels,
        [by_name[name].stats["gmd"].mean for name in labels],
        [by_name[name].stats["gmd"].ci_low for name in labels],
        [by_name[name].stats["gmd"].ci_high for name in labels],
        "几何平均直径 GMD",
        "GMD (mm)",
        result.reference,
    )
    _panel(
        axes[2],
        labels,
        [by_name[name].stats["cmi"].mean for name in labels],
        [by_name[name].stats["cmi"].ci_low for name in labels],
        [by_name[name].stats["cmi"].ci_high for name in labels],
        "碳库管理指数 CMI",
        "CMI（参照 = 100）",
        result.reference,
    )
    axes[2].axhline(100.0, color="#8a8a8a", linestyle="--", linewidth=0.9)
    figure.suptitle(
        f"团聚体稳定性与碳库管理指数（均值与 bootstrap {result.confidence:.0%} 置信区间）",
        fontsize=12,
    )
    figure.tight_layout()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(target, bbox_inches="tight")
    plt.close(figure)
    return target
