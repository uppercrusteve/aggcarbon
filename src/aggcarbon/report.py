"""Output serialization and the Chinese laboratory report template."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from aggcarbon import __version__
from aggcarbon.compute import SUMMARY_COLUMNS, ComputeResult
from aggcarbon.io import AGGREGATE_CLASSES, CLASS_DIAMETER_MM

STOCK_COLUMNS: tuple[str, ...] = (
    "sample_id",
    "treatment",
    "block",
    "aggregate_class_mm",
    "mean_diameter_mm",
    "proportion",
    "soc_g_kg",
    "soil_mass_Mg_ha",
    "esm_factor",
    "stock_Mg_ha",
    "poc_stock_Mg_ha",
    "maoc_stock_Mg_ha",
)


def _fmt(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "NA"
    return f"{value:.{digits}f}"


def _clean(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    return value


def write_summary_csv(result: ComputeResult, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in result.summary_rows():
        rows.append({column: row[column] for column in SUMMARY_COLUMNS})
    pd.DataFrame(rows, columns=list(SUMMARY_COLUMNS)).to_csv(
        target, index=False, encoding="utf-8", float_format="%.6f"
    )
    return target


def write_stocks_csv(result: ComputeResult, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "sample_id": item.sample_id,
            "treatment": item.treatment,
            "block": item.block,
            "aggregate_class_mm": item.aggregate_class,
            "mean_diameter_mm": CLASS_DIAMETER_MM[item.aggregate_class],
            "proportion": item.proportion,
            "soc_g_kg": item.soc_g_kg,
            "soil_mass_Mg_ha": item.soil_mass_mg_ha,
            "esm_factor": item.esm_factor,
            "stock_Mg_ha": item.stock_mg_ha,
            "poc_stock_Mg_ha": item.poc_stock_mg_ha,
            "maoc_stock_Mg_ha": item.maoc_stock_mg_ha,
        }
        for item in result.class_stocks
    ]
    pd.DataFrame(rows, columns=list(STOCK_COLUMNS)).to_csv(
        target, index=False, encoding="utf-8", float_format="%.6f"
    )
    return target


def write_result_json(result: ComputeResult, path: str | Path, data_note: str) -> Path:
    payload = {
        "tool": "aggcarbon",
        "version": __version__,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_note": data_note,
        "reference_treatment": result.reference,
        "reference_mass_Mg_ha": result.reference_mass_mg_ha,
        "bootstrap_replicates": result.bootstrap,
        "seed": result.seed,
        "confidence": result.confidence,
        "units": {
            "mwd": "mm",
            "gmd": "mm",
            "r025": "fraction",
            "soc_stock": "Mg/ha",
            "poc_stock": "Mg/ha",
            "maoc_stock": "Mg/ha",
            "poc_maoc_ratio": "g/g",
            "cpi": "ratio",
            "cmi": "index (reference = 100)",
        },
        "warnings": list(result.warnings),
        "treatments": [
            {
                "treatment": item.treatment,
                "n_samples": item.n_samples,
                "n_blocks": item.n_blocks,
                "metrics": {
                    name: {
                        "mean": stat.mean,
                        "sd": stat.sd,
                        "ci_low": stat.ci_low,
                        "ci_high": stat.ci_high,
                    }
                    for name, stat in {**item.stats, "cpi": item.stats["cpi"], "cmi": item.stats["cmi"]}.items()
                },
            }
            for item in result.summaries
        ],
        "samples": [
            {
                "sample_id": sample.sample_id,
                "treatment": sample.treatment,
                "block": sample.block,
                "mwd_mm": sample.mwd,
                "gmd_mm": sample.gmd,
                "r_gt_0.25": sample.r025,
                "soil_mass_Mg_ha": sample.soil_mass_mg_ha,
                "esm_factor": sample.esm_factor,
                "soc_stock_Mg_ha": sample.soc_stock,
                "poc_stock_Mg_ha": sample.poc_stock,
                "maoc_stock_Mg_ha": sample.maoc_stock,
                "poc_maoc_ratio": sample.poc_maoc_ratio,
            }
            for sample in result.samples
        ],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_clean(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _summary_table(result: ComputeResult) -> str:
    lines = [
        "| 处理 | n | MWD (mm) | GMD (mm) | R>0.25 | SOC (Mg/ha) | POC (Mg/ha) | MAOC (Mg/ha) | CPI | CMI |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in result.summaries:
        stats = item.stats
        lines.append(
            "| {name} | {n} | {mwd} | {gmd} | {r025} | {soc} | {poc} | {maoc} | {cpi} | {cmi} |".format(
                name=item.treatment,
                n=item.n_samples,
                mwd=f"{_fmt(stats['mwd'].mean)} [{_fmt(stats['mwd'].ci_low)}, {_fmt(stats['mwd'].ci_high)}]",
                gmd=f"{_fmt(stats['gmd'].mean)} [{_fmt(stats['gmd'].ci_low)}, {_fmt(stats['gmd'].ci_high)}]",
                r025=_fmt(stats["r025"].mean, 3),
                soc=f"{_fmt(stats['soc_stock'].mean)} [{_fmt(stats['soc_stock'].ci_low)}, {_fmt(stats['soc_stock'].ci_high)}]",
                poc=f"{_fmt(stats['poc_stock'].mean)} [{_fmt(stats['poc_stock'].ci_low)}, {_fmt(stats['poc_stock'].ci_high)}]",
                maoc=f"{_fmt(stats['maoc_stock'].mean)} [{_fmt(stats['maoc_stock'].ci_low)}, {_fmt(stats['maoc_stock'].ci_high)}]",
                cpi=f"{_fmt(stats['cpi'].mean)} [{_fmt(stats['cpi'].ci_low)}, {_fmt(stats['cpi'].ci_high)}]",
                cmi=f"{_fmt(stats['cmi'].mean)} [{_fmt(stats['cmi'].ci_low)}, {_fmt(stats['cmi'].ci_high)}]",
            )
        )
    return "\n".join(lines)


def _stock_table(result: ComputeResult) -> str:
    classes = [aggregate_class for aggregate_class in AGGREGATE_CLASSES if any(s.aggregate_class == aggregate_class for s in result.class_stocks)]
    lines = [
        "| 处理 | n | " + " | ".join(f"{name} mm" for name in classes) + " |",
        "|---|---|" + "---|" * len(classes),
    ]
    for item in result.summaries:
        members = [stock for stock in result.class_stocks if stock.treatment == item.treatment]
        counts = len({stock.sample_id for stock in members})
        values = []
        for name in classes:
            values.append(f"{_fmt(sum(stock.stock_mg_ha for stock in members if stock.aggregate_class == name) / counts)}")
        lines.append(f"| {item.treatment} | {counts} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def _proportion_lines(result: ComputeResult) -> str:
    lines = []
    for item in result.summaries:
        shares = "，".join(
            f"{name} mm {result.class_means[item.treatment][name] * 100:.1f}%"
            for name in AGGREGATE_CLASSES
        )
        lines.append(f"- {item.treatment}：{shares}")
    return "\n".join(lines)


def write_report(result: ComputeResult, path: str | Path, data_note: str, input_name: str) -> Path:
    """Write the Chinese laboratory report (rename and archive as an internal note)."""

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    esm_text = (
        f"已启用等效土壤质量（ESM）校正，参照质量 M_ref = {result.reference_mass_mg_ha:.1f} Mg/ha；"
        "每个样品的储量乘以 M_ref / M_sample。"
        if result.reference_mass_mg_ha is not None
        else "未启用 ESM 校正（等体积/等深度比较）。"
    )
    warnings = "\n".join(f"- {item}" for item in result.warnings) or "- 无。"
    body = f"""# 土壤团聚体稳定性与碳库指标计算报告

- 生成时间：{generated}
- 输入文件：`{input_name}`
- 参照处理：`{result.reference}`
- 数据说明：{data_note}
- 软件版本：aggcarbon {__version__}
- 不确定区间：{result.confidence:.0%} 百分位置信区间，处理内按 block 重采样 {result.bootstrap} 次，随机种子 {result.seed}

> 本报告由 `aggcarbon compute` 自动生成，可直接改名作为实验室内部说明；正式发表前请核对原始数据与分层容重。

## 1. 计算口径与公式

粒级固定为 {", ".join(f"`{name}`" for name in AGGREGATE_CLASSES)} mm，平均直径 d_i 依次取
4、1.5、0.625、0.125 mm（惯例近似，非实测粒径）。质量比例为：

- p_i = m_i / Σ m_i
- MWD = Σ(p_i × d_i)，单位 mm
- GMD = exp(Σ(p_i × ln d_i))，单位 mm
- R>0.25 = Σ p_i（仅 d_i > 0.25 mm 的粒级）
- M_Mg_ha = BD_g_cm3 × depth_cm × 100
- stock_i = M × p_i × SOC_i(g/kg) / 1000，单位 Mg/ha
- SOC_Mg_ha = Σ stock_i
- ESM：stock_i,ESM = stock_i × M_ref / M_sample
- CPI = POC_treat / POC_ref
- CMI = CPI × (SOC_treat / SOC_ref) × 100

参照处理的 CPI 与 CMI 固定为 100。{esm_text}

| 符号 | 含义 | 单位 |
|---|---|---|
| m_i | 第 i 粒级风干/烘干质量 | g |
| p_i | 第 i 粒级质量比例 | 0–1 |
| d_i | 粒级平均直径 | mm |
| BD | 容重 | g/cm3 |
| depth | 采样层厚 | cm |
| M | 单位面积土壤质量 | Mg/ha |
| SOC_i | 粒级有机碳浓度 | g/kg |
| POC / MAOC | 颗粒态 / 矿物结合态有机碳 | g/kg 或 Mg/ha |
| CPI / CMI | 碳库指数 / 碳库管理指数 | 比值 / 指数 |

## 2. 结果汇总

数值为处理均值 [95% CI]。

{_summary_table(result)}

平均质量比例（各类之和为 1）：

{_proportion_lines(result)}

### 2.1 粒级 SOC 储量（Mg/ha，处理内平均）

{_stock_table(result)}

## 3. 解释要点

- MWD 与 GMD 越大，通常表示大团聚体比例越高、结构越稳定；两者都应结合 R>0.25 与粒级分布解读。
- CPI 反映活性碳库（POC）相对参照的变化；CMI 同时纳入 POC 与总 SOC，100 表示与参照相当，>100 表示改善，<100 表示退化。
- 置信区间跨过 100（CMI）或与参照区间重叠时，应谨慎宣称处理效应。
- ESM 校正后储量可用于不同容重/深度样品间的等效质量比较；未校正结果仅适合相近容重与深度。

## 4. 假设与局限

1. 粒级平均直径（4、1.5、0.625、0.125 mm）是加权平均的惯例近似，不是筛孔实测中值。
2. 容重应分层实测；单一容重与固定深度会掩盖压实与砾石差异。
3. 湿筛前处理、振荡时间与筛组差异会影响质量分布，方法必须一致并在报告中注明。
4. POC/MAOC 依赖物理分组流程；分散不完全会改变二者比值。
5. CPI/CMI 依赖参照处理选择，且 CMI 的 100 基准只在该参照下有意义。
6. bootstrap 区间按 block 重采样；block 少于 2 个时区间会退化，仅作描述。
7. 储量未扣除 >2 mm 砾石与根系，也不含地下深层的完整碳库。

## 5. 警告与数据核查

{warnings}

## 6. 复现命令

```bash
aggcarbon compute {input_name} --reference {result.reference} -o <outdir> --bootstrap {result.bootstrap} --seed {result.seed}
```

## 7. 记录

- 分析人：__________
- 复核人：__________
- 日期：__________
- 备注：__________
"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target
