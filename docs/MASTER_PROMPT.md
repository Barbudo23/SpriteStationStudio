# AssetForge AI

# MASTER_PROMPT.md

**Version:** 1.0 (Frozen)

## Purpose

Generate a complete game-ready character asset pack from four reference
images.

## Production Rules

-   One Character = 10 Production Iterations = 100% Complete Asset.
-   Each iteration outputs a usable ZIP package.
-   Character identity must remain unchanged.
-   MVP assumes no manual editing.

## Required References

-   Front
-   Back
-   Left
-   Right

## Camera Library

  ID      Name           Pitch
  ------- ------------ -------
  CAM01   Front            30°
  CAM02   FrontRight       30°
  CAM03   Right            30°
  CAM04   BackRight        30°
  CAM05   Back             30°
  CAM06   BackLeft         30°
  CAM07   Left             30°
  CAM08   FrontLeft        30°

Camera, scale and framing are locked.

## Locked Properties

-   Face
-   Hair
-   Helmet
-   Armor
-   Vest
-   Backpack
-   Pouches
-   Weapon
-   Gloves
-   Boots
-   Body proportions
-   Scale
-   Lighting
-   Color palette

## Production Pipeline

Read MPI

↓

Read Manifest

↓

Validate References

↓

Generate Iteration

↓

Run QA

↓

Export

↓

Package ZIP

## Iterations

1.  Character Foundation
2.  Walk
3.  Idle
4.  Run
5.  Aim
6.  Shoot
7.  Reload
8.  Hit
9.  Death
10. Final Package

Each iteration exports: - PNG Sequence - Sprite Sheet - GIF Preview -
ZIP Package

## Output

Character_Final.zip

-   References/
-   Walk/
-   Idle/
-   Run/
-   Aim/
-   Shoot/
-   Reload/
-   Hit/
-   Death/
-   PNG/
-   SpriteSheets/
-   GIF/
-   Unity/
-   Readme.md

## QA

-   Identity preserved
-   Camera fixed
-   Scale fixed
-   Equipment preserved
-   Transparent background
-   Seamless loop
-   Unity compatible

## Success

Iteration 10 produces a complete commercial-ready archive.
