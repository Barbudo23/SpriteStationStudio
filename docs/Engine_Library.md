# AssetForge AI

# Engine_Library.md

Version: 1.0 (Frozen)

## Purpose

The Engine Library defines the internal Generation Steps (GS) executed
inside each Production Iteration. Generation Steps are internal
implementation details and are never exposed to the end user.

------------------------------------------------------------------------

# Naming

GS001 GS002 GS003 ...

Each GS performs exactly one atomic operation.

------------------------------------------------------------------------

# Standard Generation Pipeline

GS001 --- Validate Inputs - Verify Front / Back / Left / Right
references - Check image readability - Verify required files exist

GS002 --- Load Character - Create immutable character identity - Lock
face, equipment and proportions

GS003 --- Load Camera - Apply CameraLibrary.yaml - Lock pitch, yaw,
framing and scale

GS004 --- Generate Content - Execute the generation task defined by
Manifest.yaml - Example: Walk / Idle / Run

GS005 --- Internal QA - Compare against QA_Profile.yaml - Reject failed
output

GS006 --- Export - PNG Sequence - Sprite Sheet - GIF Preview

GS007 --- Package - Build Iteration_XX_Name.zip

GS008 --- Report - Write Production_Report.md - Update progress

------------------------------------------------------------------------

# Example

Production Iteration 02

GS001 ↓

GS002 ↓

GS003 ↓

GS004 ↓

GS005 ↓

GS006 ↓

GS007 ↓

GS008

↓

Iteration_02_Walk.zip

------------------------------------------------------------------------

# Design Rules

-   GS operations are reusable.
-   GS operations are independent.
-   Manifest selects which GS sequence to execute.
-   MPI starts Production Iterations only.
-   Users never interact with Generation Steps.
