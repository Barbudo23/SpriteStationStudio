from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app.animation_approval import (
    audit_approved_animation_package,
    publish_approved_animation,
    record_animation_review,
)
from app.animation_validation import AnimationManifestReport, validate_animation_manifest
from app.blender_runner import ForgeError


def require_animation_paths(manifest_value: str, source_value: str) -> tuple[Path, Path]:
    if not manifest_value.strip():
        raise ForgeError("Select animation_manifest.json.")
    if not source_value.strip():
        raise ForgeError("Select the source animated model.")
    return Path(manifest_value.strip()), Path(source_value.strip())


def inspect_animation_for_review(
    manifest_path: Path, source_path: Path
) -> AnimationManifestReport:
    return validate_animation_manifest(manifest_path, source_path)


class AnimationWorkflowWindow(tk.Toplevel):
    """Explicit review and approved-package UI over the verified v0.10 backend."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("Sprite Station Studio — Animation Workflow v0.10")
        self.geometry("820x560")
        self.minsize(720, 500)
        self.manifest_var = tk.StringVar()
        self.source_var = tk.StringVar()
        self.decision_var = tk.StringVar(value="rejected")
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="Выберите animation manifest и исходную анимированную модель."
        )
        self.loaded_manifest: Path | None = None
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="ANIMATION WORKFLOW", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Strict validation · explicit approval · atomic package · read-only audit",
        ).pack(anchor="w", pady=(2, 14))
        self._path_row(frame, "Animation manifest", self.manifest_var, self._choose_manifest)
        self._path_row(frame, "Source model", self.source_var, self._choose_source)
        ttk.Button(frame, text="VALIDATE FOR REVIEW", command=self._validate).pack(
            fill="x", pady=(4, 14)
        )

        review = ttk.LabelFrame(frame, text="Explicit decision", padding=12)
        review.pack(fill="x")
        ttk.Label(
            review,
            text="Проверьте contact sheet и параметры. Решение записывается один раз.",
        ).pack(anchor="w")
        ttk.Combobox(
            review,
            textvariable=self.decision_var,
            values=("approved", "rejected"),
            state="readonly",
        ).pack(fill="x", pady=(8, 0))

        self._path_row(frame, "Approved package", self.output_var, self._choose_output)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(12, 8))
        ttk.Button(actions, text="RECORD DECISION / PUBLISH", command=self._publish).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(actions, text="AUDIT PACKAGE…", command=self._audit).pack(
            side="left", padx=(8, 0)
        )
        ttk.Label(frame, textvariable=self.status_var, wraplength=760).pack(
            anchor="w", pady=(8, 0)
        )

    def _path_row(self, parent, label: str, variable: tk.StringVar, command) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text=label, width=20).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="…", width=3, command=command).pack(side="left", padx=(5, 0))

    def _choose_manifest(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self, filetypes=[("Animation manifest", "animation_manifest.json")]
        )
        if selected:
            self.manifest_var.set(selected)

    def _choose_source(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            filetypes=[("3D models", "*.fbx *.glb *.gltf"), ("All files", "*.*")],
        )
        if selected:
            self.source_var.set(selected)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(parent=self, title="Select package parent folder")
        if selected:
            self.output_var.set(str(Path(selected) / "approved-animation"))

    def _validate(self) -> None:
        try:
            manifest, source = require_animation_paths(
                self.manifest_var.get(), self.source_var.get()
            )
            report = inspect_animation_for_review(manifest, source)
            self.loaded_manifest = report.manifest_path
            self.status_var.set(
                f"VALID: {report.direction_count} directions × "
                f"{report.frame_count_per_direction} frames · "
                f"{report.checked_file_count} files checked."
            )
        except Exception as exc:
            self.loaded_manifest = None
            self._show_error(exc)

    def _publish(self) -> None:
        try:
            manifest, source = require_animation_paths(
                self.manifest_var.get(), self.source_var.get()
            )
            report = inspect_animation_for_review(manifest, source)
            if self.loaded_manifest != report.manifest_path:
                raise ForgeError("Validate the selected animation before recording a decision.")
            review_path = report.manifest_path.parent / "animation_review.json"
            decision = self.decision_var.get()
            if review_path.is_file():
                existing = json.loads(review_path.read_text(encoding="utf-8"))
                if existing.get("decision") != decision:
                    raise ForgeError("Immutable animation review already has another decision.")
            else:
                review_path = record_animation_review(
                    report.manifest_path, source, decision
                ).path
            if decision == "rejected":
                self.status_var.set(f"Decision recorded: rejected · {review_path}")
            else:
                if not self.output_var.get().strip():
                    raise ForgeError("Select a new approved package output directory.")
                package = publish_approved_animation(
                    review_path, Path(self.output_var.get().strip())
                )
                audit = audit_approved_animation_package(package.manifest_path)
                self.status_var.set(
                    f"APPROVED: {package.output_dir} · "
                    f"{audit.artifact_count} artifacts · audit valid."
                )
            messagebox.showinfo("Animation Workflow", self.status_var.get(), parent=self)
        except Exception as exc:
            self._show_error(exc)

    def _audit(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Approved package", "approved_animation_package.json")],
        )
        if not selected:
            return
        try:
            audit = audit_approved_animation_package(Path(selected))
            self.status_var.set(
                f"Audit valid: {audit.direction_count} directions × "
                f"{audit.frame_count_per_direction} frames, "
                f"{audit.artifact_count} artifacts."
            )
            messagebox.showinfo("Animation Package Audit", self.status_var.get(), parent=self)
        except Exception as exc:
            self._show_error(exc)

    def _show_error(self, error: Exception) -> None:
        self.status_var.set(str(error))
        messagebox.showerror("Animation Workflow", str(error), parent=self)
