# AssetForge — Stack 02 Rev00

This archive is the single working repository for subsequent development.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
python -m assetforge --project-root projects/Soldier_AK47 --provider mock
```

Show the current workflow state without generating assets:

```bash
python -m assetforge --project-root projects/Soldier_AK47 --status
```

An already completed iteration is skipped by default. Use `--force` only for an
intentional local rebuild.

## Current implementation

- Core runtime: configuration loader, state, pipeline.
- Implemented engine steps: GS001 through GS008.
- Provider-independent `BaseProvider` contract and deterministic `MockProvider`.
- Stack 02 runs the complete GS001–GS008 pipeline with a deterministic mock provider.
- Etalon1 references are stored under `assets/references/etalon1/`.
- Iteration 01 is preserved under `projects/Soldier_AK47/`.

## Important

The Front/Back/Left/Right alias mapping is provisional because source filenames do not encode direction. Confirm it before production generation.

## Release build

```bash
python scripts/build_release.py --stack Stack_02_Rev00
```
