# Contributing

## 开发环境

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pip install pytest ruff
```

## 提交前

```bash
python -m ruff check .
python -m pytest -q
```

两条命令必须零告警、全绿。新增公式或改动口径时，同时更新 `docs/methods.md`、`docs/report-template.md` 与手算夹具测试。

## 数据口径

- 粒级只能是 `>2`、`1-2`、`0.25-1`、`<0.25`，每样品四类齐全。
- 质量单位 g，碳浓度 g/kg，容重 g/cm3，深度 cm，储量 Mg/ha。
- 示例数据必须注明“合成演示”，不得伪装成实测。
- 参照处理由 `--reference` 显式给出；参照变化时报告要说明。

## Issue

请附：输入片段（可脱敏）、完整命令、退出码、期望结果与实际结果、Python 与依赖版本。涉及数值差异时先给出按 `docs/methods.md` 的手算值。

## PR

保持依赖精简；不引入 Web 框架。一个 PR 只做一件事，并在描述中贴出测试输出。
