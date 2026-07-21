# AssetForge Studio v0.8.1 Core Hotfix

## Fixed

Application startup failed with:

```text
_tkinter.TclError:
cannot use geometry manager pack inside .!frame
which already has slaves managed by grid
```

The top bar now uses `grid` consistently. The project status and version badge
are placed inside a dedicated right-side frame.

## Validation

- Python compilation
- Full automated test suite
- Geometry-manager regression test

Real GUI launch still needs confirmation on the target Windows workstation.
