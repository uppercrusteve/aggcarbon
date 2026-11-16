"""Command line interface for aggcarbon."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from aggcarbon import __version__
from aggcarbon.compute import compute_dataset
from aggcarbon.io import ValidationError, read_dataset, validate_dataset, write_template
from aggcarbon.plot import plot_aggregate_stability, plot_carbon_indices
from aggcarbon.report import write_report, write_result_json, write_stocks_csv, write_summary_csv

DEFAULT_DATA_NOTE = "未注明来源（正式报告请补充实测/公开数据/合成演示说明）"


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aggcarbon",
        description="土壤团聚体稳定性与碳库指标计算器 / aggregate stability and carbon index calculator",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    template = subparsers.add_parser(
        "template", help="写出带注释的 CSV 模板 / write a commented CSV template"
    )
    template.add_argument("-o", "--output", required=True, help="输出 CSV 路径")

    validate = subparsers.add_parser(
        "validate", help="校验输入 CSV / validate an input CSV"
    )
    validate.add_argument("input", help="输入 CSV 路径")

    compute = subparsers.add_parser(
        "compute", help="计算指标并生成报告、图表 / compute indices and outputs"
    )
    compute.add_argument("input", help="输入 CSV 路径")
    compute.add_argument("--reference", required=True, help="参照处理名称 / reference treatment")
    compute.add_argument("-o", "--output", required=True, help="输出目录 / output directory")
    compute.add_argument(
        "--reference-mass",
        type=float,
        default=None,
        metavar="Mg/ha",
        help="启用 ESM 的参照土壤质量（Mg/ha）",
    )
    compute.add_argument(
        "--bootstrap", type=int, default=2000, help="bootstrap 次数（默认 2000，至少 10）"
    )
    compute.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）")
    compute.add_argument(
        "--confidence", type=float, default=0.95, help="置信水平（默认 0.95）"
    )
    compute.add_argument(
        "--data-note", default=DEFAULT_DATA_NOTE, help="写入报告的来源说明"
    )
    compute.add_argument(
        "--quiet", action="store_true", help="不打印结果表 / suppress the console table"
    )
    return parser


def _cmd_template(args: argparse.Namespace) -> int:
    try:
        write_template(args.output)
    except OSError as exc:
        print(f"ERROR: 无法写入模板 / cannot write template: {exc}", file=sys.stderr)
        return 1
    print(f"已写出模板 / template written: {Path(args.output).resolve()}")
    print("模板中的行为合成示例，请替换为实测数据。")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        dataset = read_dataset(args.input)
        warnings = validate_dataset(dataset)
    except ValidationError as exc:
        print("校验失败 / validation failed:", file=sys.stderr)
        for message in exc.messages:
            print(f"  - {message}", file=sys.stderr)
        return 2
    blocks = len({(sample.treatment, sample.block) for sample in dataset.samples})
    print(
        f"OK: {len(dataset.samples)} samples, {len(dataset.treatments)} treatments, {blocks} blocks"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 0


def _print_table(result) -> None:
    print("处理 Treatment   n   MWD(mm)   GMD(mm)   SOC(Mg/ha)   CMI")
    for summary in result.summaries:
        stats = summary.stats
        print(
            f"{summary.treatment:<15} {summary.n_samples:>2}   "
            f"{stats['mwd'].mean:>7.3f}   {stats['gmd'].mean:>7.3f}   "
            f"{stats['soc_stock'].mean:>10.2f}   {stats['cmi'].mean:>6.1f}"
        )


def _cmd_compute(args: argparse.Namespace) -> int:
    try:
        dataset = read_dataset(args.input)
        result = compute_dataset(
            dataset,
            reference=args.reference,
            reference_mass_mg_ha=args.reference_mass,
            bootstrap=args.bootstrap,
            seed=args.seed,
            confidence=args.confidence,
        )
    except ValidationError as exc:
        print("计算失败 / computation failed:", file=sys.stderr)
        for message in exc.messages:
            print(f"  - {message}", file=sys.stderr)
        return 2

    output = Path(args.output)
    try:
        output.mkdir(parents=True, exist_ok=True)
        write_summary_csv(result, output / "summary.csv")
        write_stocks_csv(result, output / "stocks_by_class.csv")
        write_result_json(result, output / "result.json", args.data_note)
        write_report(result, output / "report.md", args.data_note, str(args.input))
        plot_aggregate_stability(result, output / "aggregate-stability.png")
        plot_carbon_indices(result, output / "carbon-indices.png")
    except OSError as exc:
        print(f"ERROR: 无法写出结果 / cannot write outputs: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        _print_table(result)
    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print(f"完成 / done. 输出目录: {output.resolve()}")
    print("文件: summary.csv, stocks_by_class.csv, result.json, report.md, *.png")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    _configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "template": _cmd_template,
        "validate": _cmd_validate,
        "compute": _cmd_compute,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
