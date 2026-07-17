# AssetForge --- CODEX_HANDOFF.md

# Project Status

Current stage: **Stack_01 complete → Preparing Stack_02_Rev00**

The project has completed architecture and foundation work. Future
development must continue from this point and **must not redesign the
architecture**.

------------------------------------------------------------------------

# Project Goal

Build a production system that generates a complete game-ready sprite
asset package from four character reference images.

Pipeline:

4 References → AssetForge Engine → 10 Production Iterations →
Character_Final.zip

------------------------------------------------------------------------

# Non‑Negotiable Rules

1.  One Character = 10 Production Iterations = 100%.
2.  One Production Iteration may contain unlimited internal Generation
    Steps.
3.  The user never sees Generation Steps.
4.  Every Production Iteration produces a usable package.
5.  Every Stack is buildable.
6.  New work is released only as Stack_XX_RevYY.
7.  Configuration over code.
8.  Engine must be AI-provider independent.
9.  Never duplicate configuration or business logic.
10. Preserve modular architecture (SOLID, DRY, KISS).

------------------------------------------------------------------------

# Repository Layout

    assetforge/
        core/
        engine/
        workflow/
        providers/
        exporters/
        qa/
        models/
        utils/

    configs/
    assets/
    docs/
    tests/
    scripts/

------------------------------------------------------------------------

# Existing Core

Completed:

-   Runner
-   Pipeline
-   Config Loader
-   State

Engine specification:

GS001 Input Validation

GS002 Character Lock

GS003 Camera Setup

GS004 Generation

GS005 QA

GS006 Export

GS007 Package

GS008 Report

------------------------------------------------------------------------

# Development Priorities

## Stack_02_Rev00

Objectives:

-   Convert GS001--GS008 into working Python modules.
-   Integrate Runner with Pipeline.
-   Implement BaseProvider and MockProvider.
-   Add unit tests.
-   Produce a runnable CLI.

Deliverable:

AssetForge_Stack_02_Rev00.zip

------------------------------------------------------------------------

# Definition of Done

A Stack is complete only if:

-   Project builds
-   Tests execute
-   Runner starts
-   Documentation updated
-   CHANGELOG updated
-   VERSION updated
-   Release ZIP created

------------------------------------------------------------------------

# Product Vision

The final MVP workflow:

1.  User uploads:

    -   Front
    -   Back
    -   Left
    -   Right

2.  AssetForge performs 10 Production Iterations automatically.

3.  Output:

Character_Final.zip

Containing:

-   PNG sequences
-   Sprite Sheets
-   GIF previews
-   Unity-ready structure
-   Metadata
-   Reports

------------------------------------------------------------------------

# Development Style

Treat this repository as a commercial software project.

Do not redesign frozen architecture unless explicitly requested.

Always minimize technical debt.

Prefer reusable modules over one-off implementations.

Every release must improve project quality.
