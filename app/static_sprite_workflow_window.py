from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app.static_sprite_workflow import run_static_sprite_workflow
from app.static_sprite_workflow_audit import audit_static_sprite_workflow
from core.batch import BatchPlanError, BatchPlanStore, record_batch_review


def require_selected_paths(plan_value: str, contact_value: str) -> tuple[Path, Path]:
    """Reject empty GUI selections before Path('') resolves to the working directory."""
    if not plan_value.strip():
        raise BatchPlanError("Select a BatchPlan JSON file.")
    if not contact_value.strip():
        raise BatchPlanError("Select a contact sheet manifest JSON file.")
    return Path(plan_value.strip()), Path(contact_value.strip())


def read_contact_item_ids(plan_path: Path, contact_manifest_path: Path) -> tuple[str, ...]:
    """Validate the selected pair and return reviewable item identities."""
    plan_path = plan_path.expanduser().resolve()
    contact_manifest_path = contact_manifest_path.expanduser().resolve()
    plan = BatchPlanStore().load(plan_path)
    try:
        contact = json.loads(contact_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchPlanError(f"Cannot read contact sheet manifest: {exc}") from exc
    if not isinstance(contact, dict):
        raise BatchPlanError("Contact sheet manifest must be a JSON object.")
    if contact.get("schemaVersion") != "1.0" or contact.get("kind") != "batch_preview_contact_sheet":
        raise BatchPlanError("Unsupported contact sheet contract.")
    if contact.get("application") != "Sprite Station Studio":
        raise BatchPlanError("Contact sheet application brand is invalid.")
    if contact.get("readOnlyReview") is not True:
        raise BatchPlanError("Contact sheet must declare readOnlyReview=true.")
    declared_plan = contact.get("plan")
    if not isinstance(declared_plan, str) or (contact_manifest_path.parent / declared_plan).resolve() != plan_path:
        raise BatchPlanError("Contact sheet does not reference the selected BatchPlan.")
    if contact.get("planId") != plan.plan_id:
        raise BatchPlanError("Contact sheet planId does not match BatchPlan.")
    raw_items = contact.get("items")
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 3:
        raise BatchPlanError("Contact sheet must contain between one and three items.")
    item_ids = []
    for item in raw_items:
        if not isinstance(item, dict) or not isinstance(item.get("itemId"), str):
            raise BatchPlanError("Contact sheet item is invalid.")
        item_ids.append(item["itemId"])
    if len(item_ids) != len(set(item_ids)) or set(item_ids) != {item.item_id for item in plan.items}:
        raise BatchPlanError("Contact sheet items do not match BatchPlan.")
    return tuple(item_ids)


class StaticSpriteWorkflowWindow(tk.Toplevel):
    """Limited GUI surface over the verified Static Sprite workflow backend."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("Sprite Station Studio — Static Sprite Workflow v0.9")
        self.geometry("820x620")
        self.minsize(720, 520)
        self.plan_var = tk.StringVar()
        self.contact_var = tk.StringVar()
        self.output_var = tk.StringVar(value="workflow/approved-static-sprites")
        self.status_var = tk.StringVar(value="Выберите BatchPlan и contact sheet manifest.")
        self.decision_vars: dict[str, tk.StringVar] = {}
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="STATIC SPRITE WORKFLOW", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Limited integration · explicit review · transactional publish · read-only audit",
        ).pack(anchor="w", pady=(2, 14))
        self._path_row(frame, "BatchPlan", self.plan_var, self._choose_plan)
        self._path_row(frame, "Contact manifest", self.contact_var, self._choose_contact)
        ttk.Button(frame, text="LOAD REVIEW ITEMS", command=self._load_items).pack(fill="x", pady=(2, 10))

        self.review_frame = ttk.LabelFrame(frame, text="Explicit decisions", padding=10)
        self.review_frame.pack(fill="both", expand=True)
        ttk.Label(
            self.review_frame,
            text="После загрузки выберите approved или rejected для каждого Preview.",
        ).pack(anchor="w")

        output_row = ttk.Frame(frame)
        output_row.pack(fill="x", pady=(12, 4))
        ttk.Label(output_row, text="Output (relative to plan)", width=24).pack(side="left")
        ttk.Entry(output_row, textvariable=self.output_var).pack(side="left", fill="x", expand=True)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(8, 6))
        ttk.Button(actions, text="BUILD APPROVED WORKFLOW", command=self._run).pack(side="left", fill="x", expand=True)
        ttk.Button(actions, text="AUDIT EXISTING…", command=self._audit_existing).pack(side="left", padx=(8, 0))
        ttk.Label(frame, textvariable=self.status_var, wraplength=760).pack(anchor="w", pady=(6, 0))

    def _path_row(self, parent, label: str, variable: tk.StringVar, command) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text=label, width=18).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="…", width=3, command=command).pack(side="left", padx=(5, 0))

    def _choose_plan(self) -> None:
        selected = filedialog.askopenfilename(parent=self, filetypes=[("BatchPlan JSON", "*.json")])
        if selected:
            self.plan_var.set(selected)

    def _choose_contact(self) -> None:
        selected = filedialog.askopenfilename(parent=self, filetypes=[("Contact manifest", "*.json")])
        if selected:
            self.contact_var.set(selected)

    def _load_items(self) -> None:
        try:
            plan_path, contact_path = require_selected_paths(
                self.plan_var.get(), self.contact_var.get()
            )
            item_ids = read_contact_item_ids(plan_path, contact_path)
            for child in self.review_frame.winfo_children():
                child.destroy()
            self.decision_vars.clear()
            for item_id in item_ids:
                row = ttk.Frame(self.review_frame)
                row.pack(fill="x", pady=3)
                ttk.Label(row, text=item_id).pack(side="left", fill="x", expand=True)
                variable = tk.StringVar(value="rejected")
                self.decision_vars[item_id] = variable
                ttk.Combobox(
                    row, textvariable=variable, values=("approved", "rejected"),
                    state="readonly", width=14,
                ).pack(side="right")
            self.status_var.set(f"Загружено Preview: {len(item_ids)}. Требуется явное решение для каждого.")
        except Exception as exc:
            self._show_error(exc)

    def _run(self) -> None:
        try:
            plan_path, contact_path = require_selected_paths(
                self.plan_var.get(), self.contact_var.get()
            )
            item_ids = read_contact_item_ids(plan_path, contact_path)
            if set(item_ids) != set(self.decision_vars):
                raise BatchPlanError("Reload review items before building the workflow.")
            decisions = {item_id: self.decision_vars[item_id].get() for item_id in item_ids}
            if "approved" not in decisions.values():
                raise BatchPlanError("Approve at least one Preview before building the workflow.")
            existing_review = contact_path.expanduser().resolve().parent / "review_decision.json"
            if existing_review.is_file():
                payload = json.loads(existing_review.read_text(encoding="utf-8"))
                recorded = {
                    item.get("itemId"): item.get("decision")
                    for item in payload.get("items", []) if isinstance(item, dict)
                }
                if recorded != decisions:
                    raise BatchPlanError(
                        "An immutable review_decision.json already exists with different decisions."
                    )
                review_path = existing_review
            else:
                review_path = record_batch_review(contact_path, plan_path, decisions).path
            result = run_static_sprite_workflow(
                review_path, plan_path, output_path=self.output_var.get().strip()
            )
            audit = audit_static_sprite_workflow(result.manifest_path)
            self.status_var.set(
                f"Готово: {result.output_dir} · approved {len(audit.approved_item_ids)} · audit valid"
            )
            messagebox.showinfo("Static Sprite Workflow", self.status_var.get(), parent=self)
        except Exception as exc:
            self._show_error(exc)

    def _audit_existing(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self, filetypes=[("Workflow manifest", "static_sprite_workflow_manifest.json")]
        )
        if not selected:
            return
        try:
            audit = audit_static_sprite_workflow(Path(selected))
            self.status_var.set(
                f"Audit valid: {len(audit.approved_item_ids)} items, {audit.checked_file_count} files."
            )
            messagebox.showinfo("Workflow Audit", self.status_var.get(), parent=self)
        except Exception as exc:
            self._show_error(exc)

    def _show_error(self, error: Exception) -> None:
        self.status_var.set(str(error))
        messagebox.showerror("Static Sprite Workflow", str(error), parent=self)
