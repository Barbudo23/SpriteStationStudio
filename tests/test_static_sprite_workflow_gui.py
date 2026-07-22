from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import messagebox
from unittest.mock import patch

from app.static_sprite_workflow_window import (
    StaticSpriteWorkflowWindow,
    read_contact_item_ids,
    require_selected_paths,
)
from app.ui.module_registry import create_default_registry
from core.batch import BatchPlanError


_TOOL_PATH = Path(__file__).resolve().parents[1] / "Tools/Invoke-StaticSpriteWorkflowSmoke.py"
_TOOL_SPEC = importlib.util.spec_from_file_location("sss_static_workflow_smoke_tool", _TOOL_PATH)
if _TOOL_SPEC is None or _TOOL_SPEC.loader is None:
    raise RuntimeError(f"Cannot load smoke tool: {_TOOL_PATH}")
_TOOL_MODULE = importlib.util.module_from_spec(_TOOL_SPEC)
_TOOL_SPEC.loader.exec_module(_TOOL_MODULE)
prepare_inputs = _TOOL_MODULE.prepare_inputs


class StaticSpriteWorkflowGuiTests(unittest.TestCase):
    def test_empty_gui_paths_are_rejected_before_resolution(self) -> None:
        with self.assertRaisesRegex(BatchPlanError, "Select a BatchPlan"):
            require_selected_paths("  ", "contact.json")
        with self.assertRaisesRegex(BatchPlanError, "Select a contact sheet"):
            require_selected_paths("plan.json", "")

    def prepare(self, root: Path) -> tuple[Path, Path]:
        return prepare_inputs(root)

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
                ("smoke-preview-1", "smoke-preview-2", "smoke-preview-3"),
            )
            payload = json.loads(contact_path.read_text(encoding="utf-8"))
            payload["application"] = "AssetForge Studio"
            contact_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(BatchPlanError, "brand"):
                read_contact_item_ids(plan_path, contact_path)

    def test_real_tk_controller_runs_approved_rejected_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path, contact_path = self.prepare(Path(tmp))
            try:
                root = tk.Tk()
            except tk.TclError as exc:
                self.skipTest(f"Tk display unavailable: {exc}")
            root.withdraw()
            window = StaticSpriteWorkflowWindow(root)
            window.withdraw()
            try:
                window.plan_var.set(str(plan_path))
                window.contact_var.set(str(contact_path))
                with (
                    patch.object(messagebox, "showinfo") as showinfo,
                    patch.object(messagebox, "showerror") as showerror,
                ):
                    window._load_items()
                    window.decision_vars["smoke-preview-1"].set("approved")
                    window.decision_vars["smoke-preview-3"].set("approved")
                    window.output_var.set("workflow/gui-controller")
                    window._run()
                showerror.assert_not_called()
                showinfo.assert_called_once()
                self.assertIn("audit valid", window.status_var.get())
                self.assertTrue(
                    (Path(tmp) / "workflow/gui-controller/static_sprite_workflow_manifest.json").is_file()
                )
            finally:
                window.destroy()
                root.destroy()


if __name__ == "__main__":
    unittest.main()
