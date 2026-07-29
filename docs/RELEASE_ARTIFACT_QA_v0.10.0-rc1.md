# Sprite Station Studio v0.10.0 RC1 — Release Artifact QA

Дата проверки: 2026-07-30.

Статус: **VERIFIED / PUBLISHED AS GITHUB PRERELEASE**.

## Artifact

| Поле | Значение |
|---|---|
| Tag | `v0.10.0-rc1` |
| Source commit | `ae88a25a51376c65ab689647027171ab8a704927` |
| ZIP | `SpriteStationStudio-v0.10.0rc1-ae88a25a.zip` |
| Размер | `44,254,082` bytes |
| SHA-256 | `5193c2e8e471c5d50e9ccc9579a1e03e7e31b3a1d35ba6fc512826bbd0cc7f6f` |
| Tracked files | `179` |
| GitHub assets | `3/3 uploaded` |
| Release status | `prerelease` |

## Clean verification

- manifest, filename, size, SHA-256 и file count — `PASS`;
- safe/portable ZIP paths, compression и extraction bounds — `PASS`;
- `python -S run.py --help` — `PASS`;
- regression внутри clean extraction — `172/172 PASS`;
- Static Sprite Workflow synthetic E2E — `PASS`;
- Animation Workflow synthetic E2E — `PASS`;
- Animation synthetic package: 4 направления × 2 кадра, audit valid.

## Physical verification

- Blender 5.1.2: реальный анимированный FBX, 8/8 кадров, 4/4 sheets;
- approved package: 16 integrity-bound artifacts, final audit `PASS`;
- Unity 6000.4.0f1: 4/4 Multiple Sprite sheets, 8/8 slices;
- Unity warnings: `0`;
- read-only preview: `true`.

## Post-publication verification

- tag разрешается точно в artifact commit;
- release помечен prerelease;
- ZIP, manifest и checksum имеют state `uploaded`;
- GitHub ZIP digest совпадает с локальным SHA-256.

Release: https://github.com/Barbudo23/SpriteStationStudio/releases/tag/v0.10.0-rc1

Stable-статус не присваивался.
