# Stack 1 Migration Report

## Changes made

1. Merged the approved scaffold and all files from `1 stack.zip` into one repository.
2. Moved runtime Python modules into the `assetforge` package.
3. Corrected imports from `state` to `assetforge.core.state`.
4. Split configuration into `configs/core` and frozen step specifications into `configs/steps`.
5. Moved prompts and engine documentation into `docs`.
6. Moved Etalon1 images into `assets/references/etalon1`.
7. Preserved Iteration 01 both unpacked and as its original ZIP package.
8. Removed the duplicate `GS008_Report (1).yaml`; it was byte-identical to `GS008_Report.yaml`.
9. Added `pyproject.toml`, `.gitignore`, package entry point, and corrected MVP runner.
10. Added a provisional reference direction mapping because source image names do not identify camera directions.

## Critical structure correction

A dedicated `configs/` directory and a package-level `assetforge/runner.py` were necessary. Mixing YAML specifications, source code, assets, and project outputs in one folder would make imports, packaging, testing, and future automation unreliable.
