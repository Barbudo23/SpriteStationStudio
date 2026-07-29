from __future__ import annotations

import ast
from pathlib import Path
import tkinter as tk
import unittest

from app.animation_workflow_window import AnimationWorkflowWindow, require_animation_paths
from app.blender_runner import ForgeError
from app.ui.module_registry import create_default_registry


class AnimationWorkflowGuiTests(unittest.TestCase):
    def test_empty_paths_are_rejected_before_resolution(self) -> None:
        with self.assertRaisesRegex(ForgeError, "animation_manifest"):
            require_animation_paths("", "unit.fbx")
        with self.assertRaisesRegex(ForgeError, "source animated model"):
            require_animation_paths("animation_manifest.json", " ")

    def test_registry_and_shell_open_separate_animation_window(self) -> None:
        modules = {module.id: module for module in create_default_registry().all()}
        self.assertTrue(modules["animation_workflow"].enabled)
        root = Path(__file__).resolve().parents[1]
        gui_source = (root / "app/gui.py").read_text(encoding="utf-8")
        window_source = (root / "app/animation_workflow_window.py").read_text(encoding="utf-8")
        ast.parse(window_source)
        self.assertIn("AnimationWorkflowWindow(self)", gui_source)
        self.assertIn("Sprite Station Studio — Animation Workflow", window_source)

    def test_real_tk_window_opens_without_error(self) -> None:
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        root.withdraw()
        window = AnimationWorkflowWindow(root)
        try:
            window.withdraw()
            self.assertIn("Animation Workflow v0.10", window.title())
            self.assertEqual(window.decision_var.get(), "rejected")
        finally:
            window.destroy()
            root.destroy()
