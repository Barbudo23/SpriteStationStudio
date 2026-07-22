from __future__ import annotations

import ast
import json
import os
import tempfile
import unittest
from pathlib import Path

from app.static_sprite_workflow_window import read_contact_item_ids
from app.ui.module_registry import create_default_registry
from core.batch import BatchItem, BatchOperation, BatchPlan, BatchPlanError, BatchPlanStore


class StaticSpriteWorkflowGuiTests(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[Path, Path]:
        items = []
        for index in range(1, 3):
            item_id = f"preview-{index}"
            output = root / "renders" / item_id
            output.mkdir(parents=True)
            (output / "Preview.png").write_bytes(b"not-read-by-loader")
            items.append(BatchItem(
                item_id=item_id, operation=BatchOperation.PREVIEW,
                source_path=f"models/unit-{index}.glb", output_path=f"renders/{item_id}",
            ))
        plan = BatchPlan.create(items, plan_id="gui-plan")
        for item in items:
            plan = plan.mark_running(item.item_id).mark_completed(
                item.item_id, f"renders/{item.item_id}/preview_manifest.json"
            )
        plan_path = root / "batch_plan.json"
        BatchPlanStore().save(plan, plan_path)
        contact_dir = root / "review/contact-sheet"
        contact_dir.mkdir(parents=True)
        contact_path = contact_dir / "contact_sheet_manifest.json"
        contact_path.write_text(json.dumps({
            "schemaVersion": "1.0", "application": "Sprite Station Studio",
            "kind": "batch_preview_contact_sheet", "planId": plan.plan_id,
            "readOnlyReview": True,
            "plan": os.path.relpath(plan_path, contact_dir).replace("\\", "/"),
            "items": [{"itemId": item.item_id} for item in items],
        }), encoding="utf-8")
        return plan_path, contact_path

    def test_registry_enables_sprite_builder_and_shell_opens_window(self) -> None:
        modules = {module.id: module for module in create_default_registry().all()}
        self.assertTrue(modules["sprite_builder"].enabled)
        root = Path(__file__).resolve().parents[1]
        gui = (root / "app/gui.py").read_text(encoding="utf-8")
        window = (root / "app/static_sprite_workflow_window.py").read_text(encoding="utf-8")
        ast.parse(window)
        self.assertIn("StaticSpriteWorkflowWindow(self)", gui)
        self.assertIn("Sprite Station Studio — Static Sprite Workflow", window)

    def test_loader_validates_plan_contact_pair_without_tk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path, contact_path = self.prepare(Path(tmp))
            self.assertEqual(
                read_contact_item_ids(plan_path, contact_path),
                ("preview-1", "preview-2"),
            )
            payload = json.loads(contact_path.read_text(encoding="utf-8"))
            payload["application"] = "AssetForge Studio"
            contact_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(BatchPlanError, "brand"):
                read_contact_item_ids(plan_path, contact_path)


if __name__ == "__main__":
    unittest.main()
