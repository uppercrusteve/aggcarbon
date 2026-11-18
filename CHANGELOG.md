# Changelog

All notable changes are documented here. Format follows Keep a Changelog.

## [Unreleased]

### Fixed

- Reference-treatment CPI is now 1 (it was 100 while every other treatment
  reported a plain ratio).
- Non-UTF-8 input exits with a readable UTF-8 hint instead of a traceback.

## [0.1.0] - 2026-11-17

### Added

- CSV validation for fixed wet-sieving aggregate classes, mass, SOC, bulk density, and depth.
- MWD, GMD, R>0.25, SOC/POC/MAOC stocks, equivalent soil mass correction, CPI, and CMI.
- Block-bootstrap percentile confidence intervals with reproducible seeds.
- `template`, `validate`, and `compute` CLI commands with non-zero error exits.
- `summary.csv`, `stocks_by_class.csv`, `result.json`, figures, and a Chinese `report.md`.
- Synthetic demo dataset, methods documentation, report template, and CI workflow.
