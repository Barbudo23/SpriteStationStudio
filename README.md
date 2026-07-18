# AssetForge — Stack 04 Rev00

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

## Provider switcher

Open the saved application switcher:

```powershell
python -m assetforge --provider-menu
```

On Windows, you can instead double-click `AssetForge_Provider_Switcher.cmd` in the
project folder.

Choose one option and press Enter:

1. Original OpenAI API
2. Codex built-in generator
3. CloseAI API

The selection is saved in `configs/local/Provider.yaml`; API keys remain only in the
ignored local `.env` file. Codex is initially active. You can also check or change the
setting directly:

```powershell
python -m assetforge --show-provider
python -m assetforge --set-provider codex
python -m assetforge --authorize-codex-generation
```

`--provider` remains a one-run override and does not change the saved setting. The
technical `mock` provider is available through this override for offline tests.
Codex upload permission is stored locally, is limited to configured project references
and prepared jobs, generates at most three images per run, and never removes human review.
Revoke it with `python -m assetforge --revoke-codex-generation`.

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

### CloseAI-compatible access

CloseAI is configured separately, so a gateway key can never be sent accidentally to
the official OpenAI endpoint (or the other way around). Put the key after
`CLOSEAI_API_KEY=` in `.env`, then perform a free model-list probe before a canary:

```powershell
python -m assetforge --provider closeai --probe-provider
python -m assetforge --manifest configs/iterations/Iteration_02_Walk.yaml `
  --provider closeai --canary --canary-camera CAM01
```

The default CloseAI model name is based on its public model catalog and can be corrected
through `CLOSEAI_IMAGE_MODEL` if the probe reports a different ID.

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
- Persistent OpenAI / Codex / CloseAI provider switcher.
- Codex Bridge with explicit canary approval and resumable camera job preparation.
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
