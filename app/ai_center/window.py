from __future__ import annotations

from pathlib import Path
from dataclasses import replace
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app.ai_center.models import AIGenerationRequest, AIProvider, AISettings
from app.ai_center.service import AICenterService
from app.ai_center.settings_store import AISettingsStore


class AICenterWindow(tk.Toplevel):
    """Small independent AI Center surface; the stable workspace remains untouched."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("AssetForge Studio — AI Center v0.8.2 Dev")
        self.geometry("760x620")
        self.minsize(680, 540)
        self.store = AISettingsStore()
        settings = self.store.load()
        self.settings = settings
        self.provider_var = tk.StringVar(value=settings.provider.value)
        self.camera_var = tk.StringVar(value="CAM01")
        self.output_var = tk.StringVar(value=str(Path.cwd() / "output" / "ai_center"))
        self.reference_vars = [tk.StringVar() for _ in range(4)]
        self.status_var = tk.StringVar(value="Ready. API keys are read from environment only.")
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="AI CENTER", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="OpenAI API · Codex Bridge · CloseAI API — all outputs require review",
        ).pack(anchor="w", pady=(2, 12))
        ttk.Label(frame, text="Provider").pack(anchor="w")
        ttk.Combobox(
            frame, textvariable=self.provider_var,
            values=[provider.value for provider in AIProvider], state="readonly",
        ).pack(fill="x", pady=(2, 8))
        ttk.Label(frame, text="Camera ID").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.camera_var).pack(fill="x", pady=(2, 8))
        ttk.Label(frame, text="Prompt").pack(anchor="w")
        self.prompt = tk.Text(frame, height=7, wrap="word")
        self.prompt.pack(fill="both", expand=True, pady=(2, 8))
        for index, variable in enumerate(self.reference_vars, start=1):
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"Reference {index}", width=12).pack(side="left")
            ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="…", width=3, command=lambda v=variable: self._choose(v)).pack(side="left")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(8, 2))
        ttk.Entry(row, textvariable=self.output_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Output…", command=self._choose_output).pack(side="left", padx=(5, 0))
        ttk.Button(frame, text="PREPARE / GENERATE", command=self._run).pack(fill="x", pady=(12, 6))
        ttk.Label(frame, textvariable=self.status_var, wraplength=700).pack(anchor="w")

    def _choose(self, variable: tk.StringVar) -> None:
        selected = filedialog.askopenfilename(parent=self, filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if selected:
            variable.set(selected)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(parent=self)
        if selected:
            self.output_var.set(selected)

    def _run(self) -> None:
        try:
            provider = AIProvider(self.provider_var.get())
            settings = replace(self.settings, provider=provider)
            self.store.save(settings)
            self.settings = settings
            references = tuple(Path(value.get()) for value in self.reference_vars if value.get().strip())
            request = AIGenerationRequest(
                prompt=self.prompt.get("1.0", "end").strip(),
                reference_paths=references,
                output_directory=Path(self.output_var.get()),
                camera_id=self.camera_var.get().strip(),
            )
            result = AICenterService(settings).execute(request)
            self.status_var.set(f"{result.status}: {result.job_file}")
            messagebox.showinfo("AI Center", self.status_var.get(), parent=self)
        except Exception as error:
            self.status_var.set(str(error))
            messagebox.showerror("AI Center", str(error), parent=self)
