# AssetForge Studio v0.8.1.1 Hotfix

## Scope

This hotfix corrects a confirmed Windows file-lock defect in the frozen SQLite asset
database component. Database connections are now closed deterministically after
initialization, writes, and queries.

## Compatibility

- The `.afs` project schema is unchanged.
- The SQLite schema remains at v1.
- Public database methods and result types are unchanged.
- No Blender, Unity, rendering, or UI behavior is changed.

## Verification

The regression suite verifies that the database file can be renamed immediately after
normal operations, which confirms that no connection keeps the file locked on Windows.
