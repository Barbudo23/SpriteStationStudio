# AssetForge — Stack 03 Rev00

Local AI asset-production pipeline. The complete GS001–GS008 workflow is implemented,
with a deterministic mock provider for safe testing and an official OpenAI GPT Image 2
provider for production canary images.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m assetforge --project-root projects/Soldier_AK47 --status
```

## First OpenAI image (safe one-view canary)

1. Copy `.env.example` to a new file named `.env`.
2. Open `.env` and put your OpenAI API key after `OPENAI_API_KEY=`.
3. Do not send the key in chat and do not commit `.env`; Git ignores it.
4. Start exactly one low-quality test image:

```powershell
python -m assetforge `
  --project-root projects/Soldier_AK47 `
  --manifest configs/iterations/Iteration_02_Walk.yaml `
  --provider openai `
  --canary `
  --canary-camera CAM01
```

The image and `Canary_Result.yaml` are written under
`projects/Soldier_AK47/canary/iteration_02/`. The result is marked
`REVIEW_REQUIRED`, and `Workflow_State.yaml` is not advanced. Full eight-view OpenAI
generation remains blocked until the canary review workflow is implemented and approved.

The provider accepts only the official `https://api.openai.com/v1` endpoint. Defaults
are `gpt-image-2`, quality `low`, size `1024x1024`, a 180-second timeout, and two SDK
retries. These values can be changed in the local `.env` file.

## Local simulation

```powershell
python -m assetforge --project-root projects/Soldier_AK47 --provider mock
python -m assetforge --project-root projects/Soldier_AK47 --plan
python -m assetforge --project-root projects/Soldier_AK47 --next
```

An already completed iteration is skipped by default. Use `--force` only for an
intentional local rebuild. Mock outputs and checkpoints are marked `SIMULATED`; they
test pipeline behavior but are not production art.

## Current implementation

- GS001–GS008 engine and local checkpoint/guard workflow.
- Approved-manifest catalog and ten-iteration plan.
- Provider-independent `BaseProvider` contract.
- Deterministic `MockProvider` for offline tests.
- Official OpenAI GPT Image 2 multi-reference provider.
- One-view paid-provider canary with mandatory human review status.
- PNG, sprite sheet, GIF, ZIP, report, and checksum export pipeline.

## Important

The Front/Back/Left/Right alias mapping is provisional because the original source
filenames did not encode direction. Confirm it visually before production generation.

## Tests and release

```powershell
python -m pytest -q
python scripts/build_release.py --stack Stack_03_Rev00
```
