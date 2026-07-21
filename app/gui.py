from __future__ import annotations

from pathlib import Path
from queue import Queue, Empty
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app.blender_runner import BlenderRunner, ForgeError, RenderRequest
from app.direction_runner import DirectionRenderRunner
from app.animation_runner import AnimationRenderRunner, AnimationRenderRequest
from app.unity_runner import UnityRunner, UnityBridgeError
from app.unity_sprite_preview import UnitySpritePreviewRunner
from app.unity_package_export import export_verified_package
from app.unity_asset_library import UnityAssetLibrary, UnityAssetRecord
from app.settings_store import SettingsStore, AppSettings
from app.task_guard import TaskGuard
from core.app_core import AssetForgeCore
from core.jobs.job_queue import Job, JobStatus
from app.image_asset_source import (
    ImageAssetRequest,
    ImageSourceError,
    build_image_asset,
)
from app.ui.module_registry import create_default_registry
from app.ui.theme import apply_theme, COLORS
from app.ai_center.window import AICenterWindow


class AssetForgeApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AssetForge Studio v0.8.3 Dev — Static Sprite Pipeline")
        self.geometry("1440x900")
        self.minsize(1120, 720)

        apply_theme(self)

        self.runner = BlenderRunner()
        self.direction_runner = DirectionRenderRunner()
        self.animation_runner = AnimationRenderRunner()
        self.unity_runner = UnityRunner()
        self.unity_sprite_preview_runner = UnitySpritePreviewRunner(self.unity_runner)
        self.unity_asset_library = UnityAssetLibrary()
        self.unity_asset_records: list[UnityAssetRecord] = []
        self.settings_store = SettingsStore()
        self.app_settings = self.settings_store.load()
        self.task_guard = TaskGuard()
        self.core = AssetForgeCore()
        self.core.events.subscribe("job.changed", self._on_core_job_changed)
        self.current_project_var = tk.StringVar(value="Проект не открыт")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.events: Queue[tuple[str, object]] = Queue()
        self.registry = create_default_registry()

        found = self.runner.find_blender()
        self.blender_var = tk.StringVar(value=str(found) if found else "")
        found_unity = self.unity_runner.find_unity()
        self.unity_var = tk.StringVar(value=str(found_unity) if found_unity else "")
        self.unity_status_var = tk.StringVar(value="Unity Bridge: поиск…")
        self.blender_bridge_text = tk.StringVar(value="● Blender Bridge: проверка…")
        self.unity_bridge_text = tk.StringVar(value="● Unity Bridge: поиск рабочих версий…")
        self.detected_unity_versions: list[tuple[str, str]] = []
        if self.app_settings.blender_executable:
            self.blender_var.set(self.app_settings.blender_executable)
        if self.app_settings.unity_executable:
            self.unity_var.set(self.app_settings.unity_executable)
        self.model_var = tk.StringVar(value=self.app_settings.last_model_path)
        self.output_var = tk.StringVar(
            value=(self.app_settings.last_output_path or str(Path(__file__).resolve().parents[1] / "output"))
        )
        self.resolution_var = tk.IntVar(value=512)
        self.engine_var = tk.StringVar(value="AUTO")
        self.camera_profile_var = tk.StringVar(value="Strategy30")
        self.lighting_profile_var = tk.StringVar(value="GameDefault")
        self.direction_set_var = tk.StringVar(value="4 направления")
        self.animation_enabled_var = tk.BooleanVar(value=False)
        self.animation_frame_start_var = tk.StringVar(value="")
        self.animation_frame_end_var = tk.StringVar(value="")
        self.animation_frame_step_var = tk.IntVar(value=2)
        self.animation_max_frames_var = tk.IntVar(value=24)
        self.status_var = tk.StringVar(value="Готово к работе")
        self.module_var = tk.StringVar(value="pseudo3d_forge")
        self.source_mode_var = tk.StringVar(value="3d_model")
        self.asset_name_var = tk.StringVar(value="NewUnit")
        self.direction_image_vars = {
            "front_left": tk.StringVar(),
            "front_right": tk.StringVar(),
            "back_right": tk.StringVar(),
            "back_left": tk.StringVar(),
        }
        self.direction_image_photos: dict[str, tk.PhotoImage] = {}
        self.preview_mode_var = tk.StringVar(value="sprite_bar")
        self.last_sprite_bar_path = (
            Path(__file__).resolve().parents[1]
            / "examples" / "ui_references" / "Iteration_02_Contact_Sheet.png"
        )
        self.last_unity_preset_path: Path | None = None
        self.last_unity_preview_report_path: Path | None = None

        self.preview_photo = None
        self._build_ui()
        self._load_existing_preview()
        self.after(100, self._poll_events)
        self.after(300, self._detect_and_connect_bridges)
        self.after(450, self._restore_last_project)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_sidebar()
        self._build_workspace()
        self._build_statusbar()

    def _build_topbar(self) -> None:
        bar = ttk.Frame(self, style="Alt.TFrame", padding=(14, 9))
        bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        bar.columnconfigure(1, weight=1)

        ttk.Label(bar, text="ASSETFORGE STUDIO", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            bar,
            text="Pseudo3D Forge · Production Module",
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=18)
        right_status = ttk.Frame(bar, style="Alt.TFrame")
        right_status.grid(row=0, column=2, sticky="e")
        ttk.Label(
            right_status,
            textvariable=self.current_project_var,
            style="Muted.TLabel",
        ).grid(row=0, column=0, sticky="e", padx=(0, 12))
        ttk.Label(
            right_status,
            text="v0.8.3 Sprite Dev",
            style="Badge.TLabel",
        ).grid(row=0, column=1, sticky="e")

    def _build_sidebar(self) -> None:
        sidebar = ttk.Frame(self, style="Panel.TFrame", padding=(8, 12))
        sidebar.grid(row=1, column=0, sticky="nsw")
        sidebar.configure(width=230)
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)

        ttk.Label(sidebar, text="МОДУЛИ", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", padx=8, pady=(0, 8)
        )

        row = 1
        for module in self.registry.all():
            label = f"{module.icon}  {module.display_name}"
            button = ttk.Button(
                sidebar,
                text=label + ("" if module.enabled else "  [скоро]"),
                command=lambda mid=module.id, enabled=module.enabled:
                    self._select_module(mid, enabled),
            )
            button.grid(row=row, column=0, sticky="ew", pady=2)
            row += 1

        ttk.Separator(sidebar).grid(row=row, column=0, sticky="ew", pady=12)
        row += 1
        ttk.Button(sidebar, text="▣  Project Manager", command=self._open_project_manager).grid(row=row, column=0, sticky="ew", pady=(0, 6))
        row += 1
        ttk.Button(sidebar, text="☷  Job Queue", command=self._open_job_queue).grid(row=row, column=0, sticky="ew", pady=(0, 6))
        row += 1
        ttk.Button(sidebar, text="▦  Unity Asset Library", command=self._open_unity_asset_library).grid(row=row, column=0, sticky="ew", pady=(0, 6))
        row += 1
        ttk.Button(sidebar, text="⚙  Настройки", command=self._open_settings).grid(row=row, column=0, sticky="ew")
        row += 1
        ttk.Button(sidebar, text="+  Установить модуль").grid(
            row=row, column=0, sticky="ew", pady=(4, 0)
        )

    def _build_workspace(self) -> None:
        workspace = ttk.Panedwindow(self, orient="horizontal")
        workspace.grid(row=1, column=1, columnspan=2, sticky="nsew")

        center = ttk.Frame(workspace, style="Shell.TFrame")
        inspector = ttk.Frame(workspace, style="Panel.TFrame", width=340)
        workspace.add(center, weight=5)
        workspace.add(inspector, weight=0)

        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(1, weight=1)

        self._build_pipeline(center)
        self._build_preview_area(center)
        self._build_bottom_panel(center)
        self._build_inspector(inspector)

    def _build_pipeline(self, parent) -> None:
        pipe = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 8))
        pipe.grid(row=0, column=0, sticky="ew")
        stages = [
            ("1", "Source"),
            ("2", "Analyze"),
            ("3", "Scene"),
            ("4", "Directions"),
            ("5", "Render"),
            ("6", "Package"),
        ]
        for idx, (number, name) in enumerate(stages):
            ttk.Label(pipe, text=number, style="Badge.TLabel").pack(side="left")
            ttk.Label(pipe, text=name).pack(side="left", padx=(5, 10))
            if idx < len(stages) - 1:
                ttk.Label(pipe, text="›", style="Muted.TLabel").pack(
                    side="left", padx=(0, 10)
                )

    def _build_preview_area(self, parent) -> None:
        preview_shell = ttk.Frame(parent, style="Shell.TFrame", padding=12)
        preview_shell.grid(row=1, column=0, sticky="nsew")
        preview_shell.grid_columnconfigure(0, weight=1)
        preview_shell.grid_rowconfigure(1, weight=1)

        tabs = ttk.Frame(preview_shell, style="Shell.TFrame")
        tabs.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(tabs, text="PREVIEW", style="Section.TLabel").pack(side="left")
        for label, mode in (
            ("Render", "render"),
            ("Directions", "directions"),
            ("Animation", "animation"),
            ("Sprite Bar", "sprite_bar"),
            ("Atlas", "atlas"),
        ):
            ttk.Button(
                tabs,
                text=label,
                command=lambda value=mode: self._set_preview_mode(value),
            ).pack(side="left", padx=(8, 0))

        self.preview_canvas = tk.Canvas(
            preview_shell,
            background="#0e1115",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", lambda event: self._redraw_preview())
        self.preview_canvas.create_text(
            400, 280,
            text="Последний Sprite Bar появится здесь после обработки",
            fill=COLORS["muted"],
            font=("Segoe UI", 13),
            tags="placeholder",
        )

        toolbar = ttk.Frame(preview_shell, style="Shell.TFrame")
        toolbar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(toolbar, text="⟲").pack(side="left")
        ttk.Button(toolbar, text="100%").pack(side="left", padx=4)
        ttk.Button(toolbar, text="Fit").pack(side="left")
        ttk.Label(toolbar, text="Checkerboard · Alpha", style="Muted.TLabel").pack(
            side="right"
        )

    def _build_bottom_panel(self, parent) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

        log_frame = ttk.Frame(notebook, padding=6)
        jobs_frame = ttk.Frame(notebook, padding=10)
        output_frame = ttk.Frame(notebook, padding=10)

        notebook.add(log_frame, text="Log")
        notebook.add(jobs_frame, text="Jobs")
        notebook.add(output_frame, text="Output")

        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        self.log = tk.Text(
            log_frame,
            height=8,
            wrap="word",
            state="disabled",
            background=COLORS["field"],
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
        )
        self.log.grid(row=0, column=0, sticky="nsew")

        ttk.Label(jobs_frame, text="Очередь пуста", style="Muted.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            output_frame,
            text="Здесь появятся Preview.png, manifest.json и ZIP-пакет.",
            style="Muted.TLabel",
        ).pack(anchor="w")

    def _build_inspector(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)

        ttk.Label(parent, text="INSPECTOR", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 8)
        )

        notebook = ttk.Notebook(parent)
        notebook.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        parent.grid_rowconfigure(1, weight=1)

        source = ttk.Frame(notebook, padding=12)
        render = ttk.Frame(notebook, padding=12)
        export = ttk.Frame(notebook, padding=12)
        animation = ttk.Frame(notebook, padding=12)
        integrations = ttk.Frame(notebook, padding=12)
        notebook.add(source, text="Source")
        notebook.add(render, text="Render")
        notebook.add(export, text="Export")
        notebook.add(animation, text="Animation")
        notebook.add(integrations, text="Bridges")

        source.grid_columnconfigure(0, weight=1)

        ttk.Label(source, text="Источник ассета", style="Section.TLabel").pack(anchor="w")
        mode_frame = ttk.Frame(source)
        mode_frame.pack(fill="x", pady=(6, 12))
        ttk.Radiobutton(
            mode_frame,
            text="3D-модель",
            variable=self.source_mode_var,
            value="3d_model",
            command=self._update_source_mode,
        ).pack(side="left")
        ttk.Radiobutton(
            mode_frame,
            text="4 изображения",
            variable=self.source_mode_var,
            value="four_images",
            command=self._update_source_mode,
        ).pack(side="left", padx=(12, 0))

        self.source_3d_frame = ttk.Frame(source)
        self.source_3d_frame.pack(fill="x")
        self._path_control(
            self.source_3d_frame, "Blender", self.blender_var, self._choose_blender
        )
        self._path_control(
            self.source_3d_frame, "3D-модель", self.model_var, self._choose_model
        )

        self.source_images_frame = ttk.Frame(source)
        ttk.Label(
            self.source_images_frame,
            text="Имя ассета",
            style="Section.TLabel",
        ).pack(anchor="w", pady=(0, 5))
        ttk.Entry(
            self.source_images_frame,
            textvariable=self.asset_name_var,
        ).pack(fill="x", pady=(0, 10))

        direction_labels = (
            ("front_left", "Front Left"),
            ("front_right", "Front Right"),
            ("back_right", "Back Right"),
            ("back_left", "Back Left"),
        )
        for direction_id, label in direction_labels:
            self._direction_image_control(
                self.source_images_frame,
                direction_id,
                label,
            )

        self._path_control(source, "Папка результата", self.output_var, self._choose_output)

        ttk.Separator(source).pack(fill="x", pady=12)
        ttk.Label(source, text="Asset Analysis", style="Section.TLabel").pack(anchor="w")
        self.asset_info = ttk.Label(
            source,
            text="Файл не выбран\nMeshes: —\nArmatures: —\nMaterials: —",
            style="Muted.TLabel",
            justify="left",
        )
        self.asset_info.pack(anchor="w", pady=(7, 0))

        render.grid_columnconfigure(0, weight=1)
        self._combo(render, "Camera Profile", self.camera_profile_var,
                    ("Strategy30", "XCOM", "Commandos", "Diablo"))
        self._combo(render, "Lighting Profile", self.lighting_profile_var,
                    ("GameDefault", "SoftStudio", "OutdoorSun", "HighContrast", "NeutralBake"))
        self._combo(render, "Directions", self.direction_set_var,
                    ("1 ракурс", "4 направления", "8 направлений", "Custom"))
        self._combo(render, "Resolution", self.resolution_var, (256, 512, 1024, 2048))
        self._combo(render, "Render Engine", self.engine_var,
                    ("AUTO", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH", "CYCLES"))




        ttk.Checkbutton(
            animation,
            text="Создать анимационные спрайты",
            variable=self.animation_enabled_var,
            command=self._update_animation_mode,
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            animation,
            text=(
                "Используется активная анимация FBX/GLB. "
                "Пустые Start/End означают автоматический диапазон."
            ),
            style="Muted.TLabel",
            wraplength=290,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(animation, text="Frame Start", style="Section.TLabel").pack(anchor="w")
        ttk.Entry(animation, textvariable=self.animation_frame_start_var).pack(fill="x", pady=(4, 8))
        ttk.Label(animation, text="Frame End", style="Section.TLabel").pack(anchor="w")
        ttk.Entry(animation, textvariable=self.animation_frame_end_var).pack(fill="x", pady=(4, 8))
        self._combo(animation, "Frame Step", self.animation_frame_step_var, (1, 2, 3, 4, 5, 6))
        self._combo(animation, "Max Frames / Direction", self.animation_max_frames_var, (8, 12, 16, 24, 32, 48, 64))
        ttk.Label(
            animation,
            text="Результат: PNG frames + sprite sheet для каждого направления + manifest + ZIP.",
            style="Muted.TLabel",
            wraplength=290,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))


        integrations.grid_columnconfigure(0, weight=1)
        ttk.Label(integrations, text="Состояние мостов", style="Section.TLabel").pack(anchor="w")

        self.blender_bridge_marker = ttk.Label(
            integrations,
            textvariable=self.blender_bridge_text,
            style="BridgeChecking.TLabel",
        )
        self.blender_bridge_marker.pack(anchor="w", pady=(8, 3))

        self.unity_bridge_marker = ttk.Label(
            integrations,
            textvariable=self.unity_bridge_text,
            style="BridgeChecking.TLabel",
        )
        self.unity_bridge_marker.pack(anchor="w", pady=(0, 10))

        ttk.Separator(integrations).pack(fill="x", pady=(0, 10))
        ttk.Label(integrations, text="Unity Editor", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            integrations,
            text="Автоматический поиск всех версий Unity Hub с проверкой работоспособности.",
            style="Muted.TLabel",
            wraplength=290,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))

        self.unity_versions_combo = ttk.Combobox(
            integrations,
            state="readonly",
            values=[],
        )
        self.unity_versions_combo.pack(fill="x", pady=(0, 6))
        self.unity_versions_combo.bind(
            "<<ComboboxSelected>>",
            self._on_unity_version_selected,
        )

        ttk.Button(
            integrations,
            text="НАЙТИ И ПОДКЛЮЧИТЬ МОСТЫ",
            command=self._detect_and_connect_bridges,
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            integrations,
            text="ВЫБРАТЬ UNITY.EXE ВРУЧНУЮ",
            command=self._choose_unity,
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            integrations,
            text="АНАЛИЗИРОВАТЬ МОДЕЛЬ В UNITY",
            command=self._analyze_model_with_unity,
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            integrations,
            text="UNITY IMPORT PREVIEW (READ-ONLY)",
            command=self._preview_unity_sprite_import,
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            integrations,
            text="EXPORT VERIFIED PACKAGE TO UNITY",
            command=self._export_verified_unity_package,
        ).pack(fill="x", pady=(0, 8))
        ttk.Label(
            integrations,
            textvariable=self.unity_status_var,
            style="Muted.TLabel",
            wraplength=290,
            justify="left",
        ).pack(anchor="w")

        ttk.Label(export, text="Форматы", style="Section.TLabel").pack(anchor="w")
        for text in ("PNG Frames", "GIF Preview", "Sprite Sheet", "JSON Manifest", "ZIP Package"):
            var = tk.BooleanVar(value=True if text in ("PNG Frames", "JSON Manifest", "ZIP Package") else False)
            ttk.Checkbutton(export, text=text, variable=var).pack(anchor="w", pady=2)

        ttk.Separator(parent).grid(row=2, column=0, sticky="ew", padx=10, pady=6)
        self.render_button = ttk.Button(
            parent, text="СОЗДАТЬ PREVIEW", style="Primary.TButton",
            command=self._run_primary_action
        )
        self.render_button.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 6))
        ttk.Button(
            parent, text="Открыть папку результата", command=self._open_output
        ).grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))

        # Source mode depends on widgets created above, including render_button.
        self._update_source_mode()

    def _path_control(self, parent, label, variable, command) -> None:
        ttk.Label(parent, text=label, style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 10))
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="…", width=3, command=command).pack(side="left", padx=(5, 0))

    def _combo(self, parent, label, variable, values) -> None:
        ttk.Label(parent, text=label, style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        ttk.Combobox(
            parent, textvariable=variable, values=values, state="readonly"
        ).pack(fill="x", pady=(0, 11))

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self, style="Alt.TFrame", padding=(10, 5))
        bar.grid(row=2, column=0, columnspan=3, sticky="ew")
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="●", foreground=COLORS["success"]).grid(row=0, column=0)
        ttk.Label(bar, textvariable=self.status_var, style="Muted.TLabel").grid(
            row=0, column=1, sticky="w", padx=6
        )
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=220)
        self.progress.grid(row=0, column=2, sticky="e")

    def _select_module(self, module_id: str, enabled: bool) -> None:
        if not enabled:
            messagebox.showinfo(
                "Модуль в разработке",
                "Модуль зарегистрирован в оболочке, но пока не подключён."
            )
            return
        self.module_var.set(module_id)
        if module_id == "dashboard":
            messagebox.showinfo("Dashboard", "Dashboard будет добавлен следующим этапом.")
        elif module_id == "ai_center":
            AICenterWindow(self)

    def _update_source_mode(self) -> None:
        mode = self.source_mode_var.get()
        if mode == "four_images":
            self.source_3d_frame.pack_forget()
            self.source_images_frame.pack(fill="x", after=self.source_3d_frame)
            if hasattr(self, "render_button"):
                self.render_button.configure(text="СОЗДАТЬ IMAGE ASSET ZIP")
            self.status_var.set("Режим: четыре изображения, Blender не используется")
            self.asset_info.configure(
                text="Image Source\nРакурсы: 0/4\nBlender: не требуется"
            )
        else:
            self.source_images_frame.pack_forget()
            self.source_3d_frame.pack(fill="x")
            if hasattr(self, "render_button"):
                self.render_button.configure(text="СОЗДАТЬ PREVIEW")
            self.status_var.set("Режим: 3D-модель через Blender")

    def _direction_image_control(
        self,
        parent,
        direction_id: str,
        label: str,
    ) -> None:
        ttk.Label(parent, text=label, style="Section.TLabel").pack(
            anchor="w", pady=(0, 5)
        )
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))
        ttk.Entry(
            row,
            textvariable=self.direction_image_vars[direction_id],
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            row,
            text="…",
            width=3,
            command=lambda d=direction_id: self._choose_direction_image(d),
        ).pack(side="left", padx=(5, 0))

    def _choose_direction_image(self, direction_id: str) -> None:
        value = filedialog.askopenfilename(
            title=f"Выберите изображение: {direction_id}",
            filetypes=[
                ("Изображения", "*.png *.jpg *.jpeg *.webp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("WebP", "*.webp"),
                ("Все файлы", "*.*"),
            ],
        )
        if not value:
            return

        self.direction_image_vars[direction_id].set(value)
        selected = sum(
            1 for var in self.direction_image_vars.values()
            if var.get().strip()
        )
        self.asset_info.configure(
            text=(
                f"Image Source\\n"
                f"Ракурсы: {selected}/4\\n"
                f"Последний: {Path(value).name}\\n"
                f"Blender: не требуется"
            )
        )
        self.status_var.set(f"Загружено изображений: {selected}/4")
        self._load_preview(Path(value))


    def _update_animation_mode(self) -> None:
        if self.animation_enabled_var.get():
            self.render_button.configure(text="СОЗДАТЬ ANIMATION SPRITES")
            self.status_var.set("Режим: анимация с 4/8 направлений")
            self.preview_mode_var.set("animation")
        else:
            self._update_source_mode()

    @staticmethod
    def _optional_int(value: str, field_name: str) -> int | None:
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} должен быть целым числом.") from exc

    def _run_primary_action(self) -> None:
        if self.source_mode_var.get() == "four_images":
            self._build_image_asset()
            return

        direction_mode = self.direction_set_var.get()
        if self.animation_enabled_var.get():
            if direction_mode not in {"4 направления", "8 направлений"}:
                messagebox.showwarning(
                    "Animation Sprites",
                    "Для анимации выберите 4 или 8 направлений.",
                )
                return
            self._start_animation_render(
                4 if direction_mode.startswith("4") else 8
            )
            return
        if direction_mode in {"4 направления", "8 направлений"}:
            self._start_direction_render(4 if direction_mode.startswith("4") else 8)
        else:
            self._start_render()

    def _build_image_asset(self) -> None:
        try:
            request = ImageAssetRequest(
                asset_name=self.asset_name_var.get(),
                images={
                    key: Path(var.get().strip())
                    for key, var in self.direction_image_vars.items()
                },
                output_dir=Path(self.output_var.get().strip()),
            )
            result = build_image_asset(request)
        except (ImageSourceError, OSError, ValueError) as exc:
            messagebox.showerror("Ошибка Image Source", str(exc))
            return

        self.status_var.set("Image Asset ZIP успешно создан")
        self._append_log("=" * 72)
        self._append_log("IMAGE SOURCE MODE")
        self._append_log("Blender: not used")
        for direction, var in self.direction_image_vars.items():
            self._append_log(f"{direction}: {var.get()}")
        self._append_log(f"Manifest: {result.manifest_path}")
        self._append_log(f"ZIP: {result.zip_path}")
        messagebox.showinfo(
            "Image Asset готов",
            f"ZIP создан без Blender:\\n{result.zip_path}"
        )




    def _save_settings(self) -> None:
        self.app_settings = AppSettings(
            blender_executable=self.blender_var.get().strip(),
            unity_executable=self.unity_var.get().strip(),
            last_model_path=self.model_var.get().strip(),
            last_output_path=self.output_var.get().strip(),
            last_unity_project=self.app_settings.last_unity_project,
            last_assetforge_project=(
                self.core.current_project.descriptor_path.as_posix()
                if self.core.current_project else self.app_settings.last_assetforge_project
            ),
        )
        try:
            self.settings_store.save(self.app_settings)
        except OSError as exc:
            self._append_log(f"Settings save warning: {exc}")

    def _on_close(self) -> None:
        self._save_settings()
        self.core.close()
        self.destroy()

    @staticmethod
    def _window_alive(window) -> bool:
        try:
            return bool(window.winfo_exists())
        except tk.TclError:
            return False

    def _set_bridge_marker(
        self,
        bridge: str,
        connected: bool | None,
        text: str,
    ) -> None:
        if connected is True:
            style = "BridgeOnline.TLabel"
        elif connected is False:
            style = "BridgeOffline.TLabel"
        else:
            style = "BridgeChecking.TLabel"

        value = f"● {text}"
        if bridge == "unity":
            self.unity_bridge_text.set(value)
            self.unity_bridge_marker.configure(style=style)
        else:
            self.blender_bridge_text.set(value)
            self.blender_bridge_marker.configure(style=style)

    def _detect_and_connect_bridges(self) -> None:
        token = self.task_guard.begin("bridge_detection")
        if token is None:
            self.status_var.set("Проверка мостов уже выполняется…")
            return

        self._set_bridge_marker("blender", None, "Blender Bridge: проверка…")
        self._set_bridge_marker("unity", None, "Unity Bridge: поиск рабочих версий…")
        self.status_var.set("Автоматическое подключение мостов…")
        self.progress.start(10)

        def worker() -> None:
            try:
                blender_path = None
                blender_value = self.blender_var.get().strip()
                if blender_value:
                    candidate = Path(blender_value).expanduser()
                    if candidate.is_file():
                        blender_path = candidate.resolve()
                if blender_path is None:
                    detected = self.runner.find_blender()
                    if detected and detected.is_file():
                        blender_path = detected.resolve()

                working_unity = self.unity_runner.find_working_installations()
                payload = {
                    "token": token,
                    "blender_path": str(blender_path) if blender_path else "",
                    "unity_working": [
                        {
                            "version": item.version or "unknown",
                            "path": str(item.executable),
                        }
                        for item in working_unity
                    ],
                }
                self.events.put(("bridges_detected", payload))
            except Exception as exc:
                self.events.put((
                    "bridges_detection_error",
                    {"token": token, "message": str(exc)},
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _on_unity_version_selected(self, _event=None) -> None:
        index = self.unity_versions_combo.current()
        if index < 0 or index >= len(self.detected_unity_versions):
            return
        version, executable = self.detected_unity_versions[index]
        self.unity_var.set(executable)
        self._save_settings()
        self.unity_status_var.set(f"Подключена Unity {version}")
        self._set_bridge_marker(
            "unity",
            True,
            f"Unity Bridge: подключён · {version}",
        )



    def _open_unity_asset_library(self) -> None:
        window = tk.Toplevel(self)
        window.title("AssetForge Studio — Unity Asset Library")
        window.geometry("1120x700")
        window.minsize(900, 560)
        window.transient(self)

        project_var = tk.StringVar()
        search_var = tk.StringVar()
        type_var = tk.StringVar(value="Model")
        status_var = tk.StringVar(value="Поиск Unity-проектов…")
        details_var = tk.StringVar(value="Выберите ассет.")
        selected_record: dict[str, UnityAssetRecord | None] = {"value": None}
        projects: list = []
        visible_records: list[UnityAssetRecord] = []

        outer = ttk.Frame(window, padding=12)
        outer.pack(fill="both", expand=True)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(2, weight=1)

        top = ttk.Frame(outer)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        ttk.Label(top, text="Unity Project", style="Section.TLabel").grid(row=0, column=0, padx=(0, 8))
        project_combo = ttk.Combobox(top, textvariable=project_var, state="readonly")
        project_combo.grid(row=0, column=1, sticky="ew")
        ttk.Button(top, text="Добавить проект…", command=lambda: choose_project()).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(top, text="Пересканировать", command=lambda: scan_selected_project()).grid(row=0, column=3, padx=(8, 0))

        filters = ttk.Frame(outer)
        filters.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        filters.grid_columnconfigure(1, weight=1)
        ttk.Label(filters, text="Поиск").grid(row=0, column=0, padx=(0, 8))
        search_entry = ttk.Entry(filters, textvariable=search_var)
        search_entry.grid(row=0, column=1, sticky="ew")
        ttk.Label(filters, text="Тип").grid(row=0, column=2, padx=(12, 6))
        type_combo = ttk.Combobox(
            filters,
            textvariable=type_var,
            state="readonly",
            values=["All", "Model", "Prefab", "Animation", "Texture", "Material", "Scene"],
            width=14,
        )
        type_combo.grid(row=0, column=3)

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew")

        left = ttk.Frame(body, padding=6)
        right = ttk.Frame(body, padding=12)
        body.add(left, weight=3)
        body.add(right, weight=2)

        columns = ("type", "name", "path", "size")
        tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        tree.heading("type", text="Тип")
        tree.heading("name", text="Название")
        tree.heading("path", text="Unity Path")
        tree.heading("size", text="Размер")
        tree.column("type", width=90, stretch=False)
        tree.column("name", width=220)
        tree.column("path", width=440)
        tree.column("size", width=90, anchor="e", stretch=False)
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(right, text="Asset Details", style="Section.TLabel").pack(anchor="w")
        preview = tk.Label(
            right,
            text="MODEL\nPREVIEW",
            bg="#111827",
            fg="#94A3B8",
            width=36,
            height=14,
            relief="groove",
        )
        preview.pack(fill="x", pady=(8, 10))
        details_label = ttk.Label(
            right,
            textvariable=details_var,
            justify="left",
            wraplength=360,
        )
        details_label.pack(anchor="w", fill="x")

        button_frame = ttk.Frame(right)
        button_frame.pack(fill="x", pady=(16, 0))
        use_button = ttk.Button(
            button_frame,
            text="ЗАГРУЗИТЬ В PSEUDO3D FORGE",
            state="disabled",
        )
        use_button.pack(fill="x", pady=(0, 6))
        analyze_button = ttk.Button(
            button_frame,
            text="АНАЛИЗИРОВАТЬ ЧЕРЕЗ UNITY",
            state="disabled",
        )
        analyze_button.pack(fill="x")

        ttk.Label(outer, textvariable=status_var, style="Muted.TLabel").grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )

        preview_image = {"value": None}

        def format_size(value: int) -> str:
            units = ["B", "KB", "MB", "GB"]
            size = float(value)
            for unit in units:
                if size < 1024 or unit == units[-1]:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{value} B"

        def refresh_tree(*_args) -> None:
            nonlocal visible_records
            for item in tree.get_children():
                tree.delete(item)
            visible_records = self.unity_asset_library.filter_records(
                self.unity_asset_records,
                search_var.get(),
                type_var.get(),
            )
            for index, record in enumerate(visible_records):
                tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        record.asset_type,
                        record.name,
                        record.unity_path,
                        format_size(record.size_bytes),
                    ),
                )
            status_var.set(
                f"Показано ассетов: {len(visible_records)} / {len(self.unity_asset_records)}"
            )

        def show_selected(_event=None) -> None:
            selection = tree.selection()
            if not selection:
                return
            index = int(selection[0])
            if index >= len(visible_records):
                return
            record = visible_records[index]
            selected_record["value"] = record
            details_var.set(
                f"Название: {record.name}\n"
                f"Тип: {record.asset_type}\n"
                f"Расширение: {record.extension}\n"
                f"Unity Path: {record.unity_path}\n"
                f"GUID: {record.guid or '—'}\n"
                f"Размер: {format_size(record.size_bytes)}\n"
                f"Файл: {record.absolute_path}"
            )

            can_use = record.asset_type == "Model" and record.extension in {
                ".fbx", ".obj", ".blend", ".gltf", ".glb"
            }
            use_button.configure(state="normal" if can_use else "disabled")
            analyze_button.configure(state="normal" if can_use else "disabled")

            if record.asset_type == "Texture":
                try:
                    image = Image.open(record.absolute_path)
                    image.thumbnail((340, 240), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(image)
                    preview.configure(image=photo, text="")
                    preview_image["value"] = photo
                except Exception:
                    preview.configure(image="", text="TEXTURE\nPREVIEW ERROR")
                    preview_image["value"] = None
            else:
                preview.configure(
                    image="",
                    text=f"{record.asset_type.upper()}\n{record.extension.upper()}\n\n{record.name}",
                )
                preview_image["value"] = None

        def use_selected() -> None:
            record = selected_record["value"]
            if not record:
                return
            self.model_var.set(record.absolute_path)
            self._save_settings()
            self._append_log(
                f"Loaded from Unity Asset Library: {record.unity_path}"
            )
            self.status_var.set(f"Модель загружена из Unity: {record.name}")
            self.asset_info.configure(
                text=(
                    f"{record.name}\n"
                    f"Unity Asset Library\n"
                    f"{record.unity_path}\n"
                    f"{record.extension.upper()}"
                )
            )
            window.destroy()

        def analyze_selected() -> None:
            record = selected_record["value"]
            if not record:
                return
            self.model_var.set(record.absolute_path)
            window.destroy()
            self._analyze_model_with_unity()

        use_button.configure(command=use_selected)
        analyze_button.configure(command=analyze_selected)

        def load_project(project_path: Path, force_scan: bool = False) -> None:
            status_var.set("Индексирование Unity Assets…")
            window.update_idletasks()

            cached = [] if force_scan else self.unity_asset_library.read_cache(project_path)
            if cached:
                self.unity_asset_records = cached
                refresh_tree()
                status_var.set(
                    f"Загружен кэш: {len(cached)} ассетов. "
                    "Нажмите «Пересканировать» для обновления."
                )
                return

            def worker() -> None:
                try:
                    records = self.unity_asset_library.scan_project(project_path)
                    self.events.put((
                        "unity_library_scan_ok",
                        {
                            "records": records,
                            "window": window,
                            "callback": lambda: (
                                refresh_tree(),
                                status_var.set(f"Индексировано ассетов: {len(records)}"),
                            ),
                        },
                    ))
                except Exception as exc:
                    self.events.put((
                        "unity_library_scan_error",
                        {
                            "window": window,
                            "message": str(exc),
                            "callback": lambda: status_var.set("Ошибка индексирования"),
                        },
                    ))

            threading.Thread(target=worker, daemon=True).start()

        def project_selected(_event=None) -> None:
            index = project_combo.current()
            if index < 0 or index >= len(projects):
                return
            self.app_settings.last_unity_project = projects[index].path
            self._save_settings()
            load_project(Path(projects[index].path))

        def scan_selected_project() -> None:
            index = project_combo.current()
            if index < 0 or index >= len(projects):
                messagebox.showwarning("Unity Asset Library", "Сначала выберите проект Unity.")
                return
            load_project(Path(projects[index].path), force_scan=True)

        def choose_project() -> None:
            selected = filedialog.askdirectory(title="Выберите корневую папку Unity-проекта")
            if not selected:
                return
            path = Path(selected)
            if not self.unity_asset_library.is_unity_project(path):
                messagebox.showerror(
                    "Unity Asset Library",
                    "В выбранной папке не найдены Assets и ProjectSettings.",
                )
                return
            project = self.unity_asset_library._project_from_path(path)
            if project and all(project.path != item.path for item in projects):
                projects.insert(0, project)
                project_combo.configure(
                    values=[
                        f"{item.name} · Unity {item.unity_version or 'unknown'} · {item.path}"
                        for item in projects
                    ]
                )
            project_combo.current(0)
            load_project(path)

        project_combo.bind("<<ComboboxSelected>>", project_selected)
        tree.bind("<<TreeviewSelect>>", show_selected)
        tree.bind("<Double-1>", lambda _event: use_selected())
        search_var.trace_add("write", refresh_tree)
        type_combo.bind("<<ComboboxSelected>>", refresh_tree)

        def apply_projects(found) -> None:
            nonlocal projects
            if not self._window_alive(window):
                return
            projects[:] = list(found)
            project_combo.configure(
                values=[
                    f"{item.name} · Unity {item.unity_version or 'unknown'} · {item.path}"
                    for item in projects
                ]
            )
            if projects:
                preferred = self.app_settings.last_unity_project
                index = 0
                if preferred:
                    for item_index, item in enumerate(projects):
                        if item.path == preferred:
                            index = item_index
                            break
                project_combo.current(index)
                project_var.set(project_combo.get())
                load_project(Path(projects[index].path))
            else:
                status_var.set(
                    "Unity-проекты автоматически не найдены. "
                    "Нажмите «Добавить проект…»."
                )

        def discover_projects() -> None:
            status_var.set("Поиск Unity-проектов в фоне…")

            def worker() -> None:
                try:
                    found = self.unity_asset_library.find_projects()
                    self.events.put((
                        "unity_projects_found",
                        {
                            "window": window,
                            "projects": found,
                            "callback": apply_projects,
                        },
                    ))
                except Exception as exc:
                    self.events.put((
                        "unity_library_scan_error",
                        {
                            "window": window,
                            "message": str(exc),
                            "callback": lambda: status_var.set("Ошибка поиска проектов"),
                        },
                    ))

            threading.Thread(target=worker, daemon=True).start()

        window.after(100, discover_projects)



    def _on_core_job_changed(self, event) -> None:
        try:
            self.events.put(("core_job_changed", event.payload))
        except Exception:
            pass

    def _activate_project(self, project) -> None:
        self.core.activate_project(project)
        self.current_project_var.set(f"Проект: {project.name}")
        self.output_var.set(str(Path(project.root_path) / "Export"))
        self._save_settings()
        self._append_log(f"Project activated: {project.descriptor_path}")

    def _open_project_manager(self) -> None:
        window = tk.Toplevel(self)
        window.title("AssetForge Studio — Project Manager")
        window.geometry("760x340")
        window.transient(self)

        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="AssetForge Projects", style="Section.TLabel").pack(anchor="w")

        status = ttk.Label(
            frame,
            textvariable=self.current_project_var,
            style="Muted.TLabel",
        )
        status.pack(anchor="w", pady=(6, 16))

        def create_project() -> None:
            parent = filedialog.askdirectory(title="Папка для нового проекта")
            if not parent:
                return
            dialog = tk.Toplevel(window)
            dialog.title("Новый проект")
            dialog.geometry("420x150")
            dialog.transient(window)
            content = ttk.Frame(dialog, padding=14)
            content.pack(fill="both", expand=True)
            name_var = tk.StringVar(value="AssetForgeProject")
            ttk.Label(content, text="Название проекта").pack(anchor="w")
            entry = ttk.Entry(content, textvariable=name_var)
            entry.pack(fill="x", pady=(6, 12))
            entry.focus_set()

            def confirm() -> None:
                try:
                    project = self.core.projects.create(Path(parent), name_var.get())
                    self._activate_project(project)
                    dialog.destroy()
                    window.destroy()
                except Exception as exc:
                    messagebox.showerror("Project Manager", str(exc))

            ttk.Button(content, text="СОЗДАТЬ", command=confirm).pack(fill="x")

        def open_project() -> None:
            descriptor = filedialog.askopenfilename(
                title="Открыть AssetForge Project",
                filetypes=[("AssetForge Project", "*.afs"), ("Все файлы", "*.*")],
            )
            if not descriptor:
                return
            try:
                project = self.core.projects.open(Path(descriptor))
                self._activate_project(project)
                window.destroy()
            except Exception as exc:
                messagebox.showerror("Project Manager", str(exc))

        ttk.Button(frame, text="СОЗДАТЬ НОВЫЙ ПРОЕКТ", command=create_project).pack(fill="x", pady=(0, 8))
        ttk.Button(frame, text="ОТКРЫТЬ .AFS ПРОЕКТ", command=open_project).pack(fill="x", pady=(0, 8))

        if self.core.current_project:
            ttk.Label(
                frame,
                text=str(self.core.current_project.descriptor_path),
                style="Muted.TLabel",
                wraplength=700,
            ).pack(anchor="w", pady=(12, 0))

    def _open_job_queue(self) -> None:
        window = tk.Toplevel(self)
        window.title("AssetForge Studio — Job Queue")
        window.geometry("900x480")
        window.transient(self)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        columns = ("status", "name", "created", "error")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for key, label, width in (
            ("status", "Status", 100),
            ("name", "Job", 260),
            ("created", "Created", 150),
            ("error", "Error", 340),
        ):
            tree.heading(key, text=label)
            tree.column(key, width=width)
        tree.pack(fill="both", expand=True)

        def refresh() -> None:
            if not self._window_alive(window):
                return
            for item in tree.get_children():
                tree.delete(item)
            for job in self.core.jobs.list_jobs():
                tree.insert(
                    "",
                    "end",
                    iid=job.id,
                    values=(
                        job.status.value,
                        job.name,
                        f"{job.created_utc:.0f}",
                        job.error or "",
                    ),
                )
            window.after(500, refresh)

        refresh()

    def _restore_last_project(self) -> None:
        descriptor = self.app_settings.last_assetforge_project
        if not descriptor:
            return
        try:
            project = self.core.projects.open(Path(descriptor))
            self._activate_project(project)
        except Exception as exc:
            self._append_log(f"Project restore warning: {exc}")


    def _open_settings(self) -> None:
        window = tk.Toplevel(self)
        window.title("AssetForge Studio — Настройки")
        window.geometry("720x300")
        window.transient(self)
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Внешние приложения", style="Section.TLabel").pack(anchor="w")
        self._path_control(frame, "Blender", self.blender_var, self._choose_blender)
        self._path_control(frame, "Unity Editor", self.unity_var, self._choose_unity)
        ttk.Label(
            frame,
            text="Указывайте Unity.exe из папки Editor, а не Unity Hub.exe.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 10))
        ttk.Button(frame, text="Проверить Unity", command=self._test_unity_bridge).pack(anchor="w")

    def _choose_unity(self) -> None:
        value = filedialog.askopenfilename(
            title="Выберите Unity Editor",
            filetypes=[("Unity Editor", "Unity.exe"), ("Все файлы", "*.*")],
        )
        if value:
            self.unity_var.set(value)
            self._save_settings()
            self.unity_status_var.set("Unity Bridge: путь выбран, требуется проверка")
            self._set_bridge_marker("unity", None, "Unity Bridge: требуется проверка")

    def _test_unity_bridge(self) -> None:
        value = self.unity_var.get().strip()
        if not value:
            messagebox.showwarning("Unity Bridge", "Укажите путь к Unity.exe.")
            return
        self.status_var.set("Проверка Unity Editor…")
        self.progress.start(10)

        def worker() -> None:
            try:
                version = self.unity_runner.query_version(Path(value))
                self.events.put(("unity_ok", version))
            except Exception as exc:
                self.events.put(("unity_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _analyze_model_with_unity(self) -> None:
        unity = self.unity_var.get().strip()
        model = self.model_var.get().strip()
        if not unity:
            messagebox.showwarning("Unity Bridge", "Укажите путь к Unity.exe.")
            return
        if not model:
            messagebox.showwarning("Unity Bridge", "Сначала выберите 3D-модель.")
            return

        output = Path(self.output_var.get().strip()).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        command_path = output / "unity_command.json"
        report_path = output / "unity_asset_report.json"
        log_path = output / "unity_bridge.log"
        project_path = Path(__file__).resolve().parents[1] / "unity_bridge_project"
        command = {
            "operation": "analyze_asset",
            "sourcePath": str(Path(model).expanduser().resolve()),
            "reportPath": str(report_path),
            "workingAssetPath": "Assets/AssetForgeInput",
        }
        command_path.write_text(json.dumps(command, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status_var.set("Unity анализирует модель в batch mode…")
        self.progress.start(10)

        def worker() -> None:
            try:
                result = self.unity_runner.execute(
                    Path(unity),
                    project_path,
                    "AssetForgeUnityBridge.Execute",
                    command_path,
                    log_path,
                )
                report = {}
                if result.report_path and result.report_path.is_file():
                    report = json.loads(result.report_path.read_text(encoding="utf-8"))
                self.events.put(("unity_analysis_ok", report))
            except Exception as exc:
                self.events.put(("unity_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()


    def _preview_unity_sprite_import(self) -> None:
        unity = self.unity_var.get().strip()
        if not unity:
            messagebox.showwarning("Unity Import Preview", "Укажите путь к Unity.exe.")
            return

        default_preset = Path(self.output_var.get().strip()) / "unity_import_preset.json"
        preset = self.last_unity_preset_path
        if preset is None or not preset.is_file():
            preset = default_preset
        if not preset.is_file():
            selected = filedialog.askopenfilename(
                title="Выберите unity_import_preset.json",
                filetypes=[("Unity Import Preset", "*.json"), ("Все файлы", "*.*")],
            )
            if not selected:
                return
            preset = Path(selected)

        token = self.task_guard.begin("unity_import_preview")
        if token is None:
            messagebox.showinfo("Unity Import Preview", "Проверка уже выполняется.")
            return
        self.status_var.set("Unity проверяет Sprite preset в read-only режиме…")
        self.progress.start(10)
        self._append_log(f"UNITY IMPORT PREVIEW: {preset}")

        def worker() -> None:
            try:
                result = self.unity_sprite_preview_runner.run(
                    Path(unity), preset, timeout=300
                )
                self.events.put(("unity_preview_ok", {"token": token, "result": result}))
            except Exception as exc:
                self.events.put(("unity_preview_error", {
                    "token": token,
                    "message": str(exc),
                }))

        threading.Thread(target=worker, daemon=True).start()


    def _export_verified_unity_package(self) -> None:
        output_dir = Path(self.output_var.get().strip())
        preset = self.last_unity_preset_path or (output_dir / "unity_import_preset.json")
        report = self.last_unity_preview_report_path or (
            output_dir / "unity_import_preview_report.json"
        )
        if not preset.is_file() or not report.is_file():
            messagebox.showwarning(
                "Unity Package Export",
                "Сначала выполните UNITY IMPORT PREVIEW (READ-ONLY).",
            )
            return

        selected = filedialog.askdirectory(
            title="Выберите Unity-проект или его папку Assets"
        )
        if not selected:
            return
        if not messagebox.askyesno(
            "Подтверждение Unity Export",
            "AssetForge создаст новую папку Assets/AssetForgeImports/<asset>.\n"
            "Существующие файлы и .meta не будут перезаписаны.\n\n"
            f"Проект: {selected}\n\nПродолжить?",
        ):
            return

        token = self.task_guard.begin("unity_package_export")
        if token is None:
            messagebox.showinfo("Unity Package Export", "Экспорт уже выполняется.")
            return
        self.status_var.set("Копирование проверенного пакета в Unity Assets…")
        self.progress.start(10)

        def worker() -> None:
            try:
                result = export_verified_package(preset, report, Path(selected))
                self.events.put(("unity_export_ok", {"token": token, "result": result}))
            except Exception as exc:
                self.events.put(("unity_export_error", {
                    "token": token,
                    "message": str(exc),
                }))

        threading.Thread(target=worker, daemon=True).start()


    def _choose_blender(self) -> None:
        types = [("Blender", "blender.exe"), ("Все файлы", "*.*")]
        value = filedialog.askopenfilename(title="Выберите Blender", filetypes=types)
        if value:
            self.blender_var.set(value)
            self._save_settings()

    def _choose_model(self) -> None:
        value = filedialog.askopenfilename(
            title="Выберите 3D-модель",
            filetypes=[
                ("3D-модели", "*.fbx *.glb *.gltf *.obj"),
                ("Все файлы", "*.*"),
            ],
        )
        if value:
            self.model_var.set(value)
            self.asset_info.configure(text=f"{Path(value).name}\nОжидает анализа Blender")
            self.status_var.set("Модель выбрана")

    def _choose_output(self) -> None:
        value = filedialog.askdirectory(title="Выберите папку результата")
        if value:
            self.output_var.set(value)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


    def _start_animation_render(self, direction_count: int) -> None:
        token = self.task_guard.begin("animation_render")
        if token is None:
            messagebox.showinfo("Animation Sprites", "Рендер анимации уже выполняется.")
            return
        try:
            frame_start = self._optional_int(
                self.animation_frame_start_var.get(), "Frame Start"
            )
            frame_end = self._optional_int(
                self.animation_frame_end_var.get(), "Frame End"
            )
            request = AnimationRenderRequest(
                blender_path=Path(self.blender_var.get().strip()),
                model_path=Path(self.model_var.get().strip()),
                output_dir=Path(self.output_var.get().strip()),
                resolution=int(self.resolution_var.get()),
                engine=self.engine_var.get(),
                direction_count=direction_count,
                frame_start=frame_start,
                frame_end=frame_end,
                frame_step=int(self.animation_frame_step_var.get()),
                max_frames=int(self.animation_max_frames_var.get()),
                camera_profile=self.camera_profile_var.get(),
            )
            self.animation_runner.build_command(request)
        except (ForgeError, ValueError, OSError) as exc:
            self.task_guard.finish(token)
            messagebox.showerror("Animation Sprites", str(exc))
            return

        self._save_settings()
        self.render_button.configure(state="disabled")
        self.progress.start(10)
        self.status_var.set(
            f"Рендер анимации: {direction_count} направлений…"
        )
        self._append_log("=" * 72)
        self._append_log("ANIMATION SPRITE RENDER")
        self._append_log(f"Model: {request.model_path}")
        self._append_log(
            f"Directions: {direction_count}; Step: {request.frame_step}; "
            f"Max frames: {request.max_frames}"
        )

        def worker() -> None:
            try:
                result = self.animation_runner.run(
                    request,
                    on_output=lambda line: self.events.put(("log", line)),
                )
                self.events.put((
                    "animation_success",
                    {"token": token, "result": result},
                ))
            except Exception as exc:
                self.events.put((
                    "animation_error",
                    {"token": token, "message": str(exc)},
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _start_direction_render(self, direction_count: int) -> None:
        try:
            request = RenderRequest(
                blender_path=Path(self.blender_var.get().strip()),
                model_path=Path(self.model_var.get().strip()),
                output_dir=Path(self.output_var.get().strip()),
                resolution=int(self.resolution_var.get()),
                engine=self.engine_var.get(),
                camera_profile=self.camera_profile_var.get(),
            )
            request.validate()
        except (ValueError, ForgeError) as exc:
            messagebox.showerror("Ошибка параметров", str(exc))
            return

        self.render_button.configure(state="disabled")
        self.progress.start(10)
        self.status_var.set(f"Рендер {direction_count} ракурсов…")
        self._append_log("=" * 72)
        self._append_log(f"DIRECTION RENDER: {direction_count}")
        self._append_log(f"Модель: {request.model_path}")

        threading.Thread(
            target=self._direction_render_thread,
            args=(request, direction_count, self.camera_profile_var.get()),
            daemon=True,
        ).start()

    def _direction_render_thread(
        self,
        request: RenderRequest,
        direction_count: int,
        camera_profile: str,
    ) -> None:
        try:
            result = self.direction_runner.run(
                request,
                direction_count,
                camera_profile,
                on_output=lambda line: self.events.put(("log", line)),
            )
            self.events.put(("direction_success", result))
        except Exception as exc:
            self.events.put(("error", exc))

    def _start_render(self) -> None:
        try:
            request = RenderRequest(
                blender_path=Path(self.blender_var.get().strip()),
                model_path=Path(self.model_var.get().strip()),
                output_dir=Path(self.output_var.get().strip()),
                resolution=int(self.resolution_var.get()),
                engine=self.engine_var.get(),
                camera_profile=self.camera_profile_var.get(),
            )
            request.validate()
        except (ValueError, ForgeError) as exc:
            messagebox.showerror("Ошибка параметров", str(exc))
            return

        self.render_button.configure(state="disabled")
        self.progress.start(10)
        self.status_var.set("Blender выполняет импорт и рендер…")
        self._append_log("=" * 72)
        self._append_log(f"Модель: {request.model_path}")
        self._append_log(f"Результат: {request.output_dir}")

        threading.Thread(
            target=self._render_thread, args=(request,), daemon=True
        ).start()

    def _render_thread(self, request: RenderRequest) -> None:
        try:
            result = self.runner.run(
                request,
                on_output=lambda line: self.events.put(("log", line)),
            )
            self.events.put(("success", result))
        except Exception as exc:
            self.events.put(("error", exc))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "core_job_changed":
                    job = payload
                    self._append_log(f"JOB {job.status.value.upper()}: {job.name}")
                elif kind == "animation_success":
                    self.progress.stop()
                    self.render_button.configure(state="normal")
                    data = payload if isinstance(payload, dict) else {}
                    token = data.get("token")
                    if token:
                        self.task_guard.finish(token)
                    result = data.get("result")
                    if result:
                        self.status_var.set("Анимационные спрайты созданы")
                        self.last_sprite_bar_path = result.contact_sheet_path
                        self.preview_mode_var.set("animation")
                        self._load_preview(result.contact_sheet_path)
                        self._append_log(f"Animation manifest: {result.manifest_path}")
                        self._append_log(f"Unity preset: {result.unity_preset_path}")
                        self.last_unity_preset_path = result.unity_preset_path
                        self.last_unity_preview_report_path = None
                        self._append_log(f"Animation ZIP: {result.zip_path}")
                        messagebox.showinfo(
                            "Animation Sprites готовы",
                            f"ZIP создан:\n{result.zip_path}",
                        )
                elif kind == "animation_error":
                    self.progress.stop()
                    self.render_button.configure(state="normal")
                    data = payload if isinstance(payload, dict) else {}
                    token = data.get("token")
                    if token:
                        self.task_guard.finish(token)
                    message = str(data.get("message", "Неизвестная ошибка"))
                    self.status_var.set("Ошибка рендера анимации")
                    self._append_log(f"Animation render error: {message}")
                    messagebox.showerror("Animation Sprites", message)
                elif kind == "unity_projects_found":
                    data = payload if isinstance(payload, dict) else {}
                    window = data.get("window")
                    callback = data.get("callback")
                    if self._window_alive(window) and callable(callback):
                        callback(data.get("projects", []))
                elif kind == "unity_library_scan_ok":
                    data = payload if isinstance(payload, dict) else {}
                    window = data.get("window")
                    records = data.get("records", [])
                    self.unity_asset_records = list(records)
                    callback = data.get("callback")
                    if (window is None or self._window_alive(window)) and callable(callback):
                        callback()
                elif kind == "unity_library_scan_error":
                    data = payload if isinstance(payload, dict) else {}
                    window = data.get("window")
                    callback = data.get("callback")
                    if (window is None or self._window_alive(window)) and callable(callback):
                        callback()
                    messagebox.showerror(
                        "Unity Asset Library",
                        str(data.get("message", "Неизвестная ошибка")),
                    )
                elif kind == "bridges_detection_error":
                    self.progress.stop()
                    data = payload if isinstance(payload, dict) else {}
                    token = data.get("token")
                    if token:
                        self.task_guard.finish(token)
                    self._set_bridge_marker("blender", False, "Blender Bridge: ошибка проверки")
                    self._set_bridge_marker("unity", False, "Unity Bridge: ошибка проверки")
                    self.status_var.set("Ошибка автоматического подключения мостов")
                    self._append_log(f"Bridge detection error: {data.get('message', 'unknown')}")
                elif kind == "bridges_detected":
                    self.progress.stop()
                    data = payload if isinstance(payload, dict) else {}
                    token = data.get("token")
                    if token:
                        self.task_guard.finish(token)
                    blender_path = data.get("blender_path", "")
                    if blender_path:
                        self.blender_var.set(blender_path)
                        self._set_bridge_marker(
                            "blender",
                            True,
                            "Blender Bridge: подключён",
                        )
                    else:
                        self._set_bridge_marker(
                            "blender",
                            False,
                            "Blender Bridge: не подключён",
                        )

                    working = data.get("unity_working", [])
                    self.detected_unity_versions = [
                        (str(item.get("version", "unknown")), str(item.get("path", "")))
                        for item in working
                        if item.get("path")
                    ]
                    labels = [
                        f"Unity {version} — {path}"
                        for version, path in self.detected_unity_versions
                    ]
                    self.unity_versions_combo.configure(values=labels)

                    if self.detected_unity_versions:
                        self.unity_versions_combo.current(0)
                        version, executable = self.detected_unity_versions[0]
                        self.unity_var.set(executable)
                        self.unity_status_var.set(
                            f"Рабочих версий: {len(self.detected_unity_versions)}. "
                            f"Активна Unity {version}"
                        )
                        self._set_bridge_marker(
                            "unity",
                            True,
                            f"Unity Bridge: подключён · {version}",
                        )
                        self._append_log(
                            f"Unity Bridge auto-connected: {version} | {executable}"
                        )
                    else:
                        self.unity_status_var.set("Рабочие версии Unity Editor не найдены")
                        self._set_bridge_marker(
                            "unity",
                            False,
                            "Unity Bridge: не подключён",
                        )
                    self.status_var.set("Проверка мостов завершена")
                    self._save_settings()
                elif kind == "unity_ok":
                    self.progress.stop()
                    version = str(payload)
                    self.unity_status_var.set(f"Unity Bridge: готов · {version}")
                    self._set_bridge_marker(
                        "unity",
                        True,
                        f"Unity Bridge: подключён · {version}",
                    )
                    self.status_var.set(f"Unity Editor подключён: {version}")
                    self._append_log(f"Unity Bridge connected: {version}")
                elif kind == "unity_analysis_ok":
                    self.progress.stop()
                    report = payload if isinstance(payload, dict) else {}
                    self.status_var.set("Unity-анализ модели завершён")
                    self.asset_info.configure(
                        text=(
                            f"{Path(report.get('sourcePath', self.model_var.get())).name}\n"
                            f"Unity: {report.get('unityVersion', '—')}\n"
                            f"Transforms: {report.get('transformCount', '—')}\n"
                            f"Skinned Meshes: {report.get('skinnedMeshCount', '—')}\n"
                            f"Animation Clips: {report.get('animationClipCount', '—')}\n"
                            f"Humanoid: {report.get('isHuman', False)}"
                        )
                    )
                    self._append_log("UNITY ASSET REPORT")
                    self._append_log(json.dumps(report, ensure_ascii=False, indent=2))
                elif kind == "unity_preview_ok":
                    self.progress.stop()
                    data = payload if isinstance(payload, dict) else {}
                    token = data.get("token")
                    if token:
                        self.task_guard.finish(token)
                    result = data.get("result")
                    report = result.report if result else {}
                    if result:
                        self.last_unity_preview_report_path = result.report_path
                    assets = report.get("spriteAssets", [])
                    valid_count = sum(1 for item in assets if item.get("valid"))
                    asset_count = int(report.get("spriteAssetCount", len(assets)))
                    slice_count = int(report.get("spriteSliceCount", 0))
                    warnings = report.get("warnings", [])
                    self.status_var.set(
                        f"Unity Import Preview: {valid_count}/{asset_count} valid"
                    )
                    self._append_log("UNITY IMPORT PREVIEW REPORT")
                    self._append_log(json.dumps(report, ensure_ascii=False, indent=2))
                    messagebox.showinfo(
                        "Unity Import Preview — Read-only",
                        f"Ассеты: {valid_count}/{asset_count} valid\n"
                        f"Slices: {slice_count}\n"
                        f"Предупреждения: {len(warnings)}\n\n"
                        "Пользовательский Unity-проект не изменялся.",
                    )
                elif kind == "unity_export_ok":
                    self.progress.stop()
                    data = payload if isinstance(payload, dict) else {}
                    token = data.get("token")
                    if token:
                        self.task_guard.finish(token)
                    result = data.get("result")
                    target = result.target_dir if result else "—"
                    count = len(result.copied_files) if result else 0
                    self.status_var.set(f"Unity package exported: {count} files")
                    self._append_log(f"UNITY PACKAGE EXPORTED: {target}")
                    messagebox.showinfo(
                        "Unity Package Export",
                        f"Скопировано файлов: {count}\n{target}\n\n"
                        "Существующие файлы не перезаписывались.",
                    )
                elif kind == "unity_export_error":
                    self.progress.stop()
                    data = payload if isinstance(payload, dict) else {}
                    token = data.get("token")
                    if token:
                        self.task_guard.finish(token)
                    message = str(data.get("message", "Неизвестная ошибка"))
                    self.status_var.set("Ошибка Unity Package Export")
                    self._append_log(f"Unity Package Export error: {message}")
                    messagebox.showerror("Unity Package Export", message)
                elif kind == "unity_preview_error":
                    self.progress.stop()
                    data = payload if isinstance(payload, dict) else {}
                    token = data.get("token")
                    if token:
                        self.task_guard.finish(token)
                    message = str(data.get("message", "Неизвестная ошибка"))
                    self.status_var.set("Ошибка Unity Import Preview")
                    self._append_log(f"Unity Import Preview error: {message}")
                    messagebox.showerror("Unity Import Preview", message)
                elif kind == "unity_error":
                    self.progress.stop()
                    self.unity_status_var.set("Unity Bridge: ошибка")
                    self._set_bridge_marker(
                        "unity",
                        False,
                        "Unity Bridge: не подключён",
                    )
                    self.status_var.set("Ошибка Unity Bridge")
                    self._append_log(f"Unity Bridge error: {payload}")
                    messagebox.showerror("Unity Bridge", str(payload))
                elif kind == "log":
                    self._append_log(str(payload))
                elif kind == "success":
                    self.progress.stop()
                    self.render_button.configure(state="normal")
                    result = payload
                    self.status_var.set("Preview успешно создан")
                    self.asset_info.configure(
                        text=(
                            f"{Path(result.report.get('source', '')).name}\n"
                            f"Meshes: {result.report.get('meshes', '?')}\n"
                            f"Armatures: {result.report.get('armatures', '?')}\n"
                            f"Materials: {result.report.get('materials', '?')}"
                        )
                    )
                    self._load_preview(result.preview_path)
                    self._append_log(f"Unity preset: {result.unity_preset_path}")
                    self.last_unity_preset_path = result.unity_preset_path
                    self.last_unity_preview_report_path = None
                    self._append_log(f"ГОТОВО: {result.preview_path}")
                elif kind == "direction_success":
                    self.progress.stop()
                    self.render_button.configure(state="normal")
                    result = payload
                    self.status_var.set(
                        f"Создан пакет: {result.report.get('directionCount', '?')} ракурсов"
                    )
                    self._register_sprite_bar(result.contact_sheet_path)
                    self.preview_mode_var.set("sprite_bar")
                    self._load_preview(result.contact_sheet_path)
                    self._append_log(f"CONTACT SHEET: {result.contact_sheet_path}")
                    self._append_log(f"Unity preset: {result.unity_preset_path}")
                    self.last_unity_preset_path = result.unity_preset_path
                    self.last_unity_preview_report_path = None
                    self._append_log(f"ZIP: {result.zip_path}")
                    messagebox.showinfo(
                        "Пакет ракурсов готов",
                        f"Создан ZIP:\n{result.zip_path}"
                    )
                elif kind == "error":
                    self.progress.stop()
                    self.render_button.configure(state="normal")
                    self.status_var.set("Ошибка")
                    self._append_log(f"ОШИБКА: {payload}")
                    messagebox.showerror("Ошибка", str(payload))
        except Empty:
            pass
        self.after(100, self._poll_events)

    def _set_preview_mode(self, mode: str) -> None:
        self.preview_mode_var.set(mode)
        if mode == "sprite_bar":
            path = Path(self.last_sprite_bar_path)
            if path.is_file():
                self._load_preview(path)
                self.status_var.set("Показан последний Sprite Bar")
            else:
                self.status_var.set("Sprite Bar ещё не создан")
        elif mode == "render":
            path = Path(self.output_var.get().strip()) / "Preview.png"
            if path.is_file():
                self._load_preview(path)
            else:
                self.status_var.set("Render Preview ещё не создан")
        else:
            self.status_var.set(f"Режим {mode} будет подключён следующим этапом")

    def _register_sprite_bar(self, path: Path) -> None:
        if path.is_file():
            self.last_sprite_bar_path = path
            if self.preview_mode_var.get() == "sprite_bar":
                self._load_preview(path)

    def _load_existing_preview(self) -> None:
        if self.preview_mode_var.get() == "sprite_bar":
            path = Path(self.last_sprite_bar_path)
            if path.is_file():
                self._load_preview(path)
                return

        path = Path(__file__).resolve().parents[1] / "output" / "Preview.png"
        if path.is_file():
            self._load_preview(path)

    def _load_preview(self, path: Path) -> None:
        try:
            image = tk.PhotoImage(file=str(path))
            self.preview_photo = image
            self.preview_canvas.delete("all")
            self._redraw_preview()
        except tk.TclError:
            self._append_log(f"Не удалось открыть изображение: {path}")

    def _redraw_preview(self) -> None:
        self.preview_canvas.delete("preview")
        if not self.preview_photo:
            return
        cw = max(self.preview_canvas.winfo_width(), 1)
        ch = max(self.preview_canvas.winfo_height(), 1)
        iw = self.preview_photo.width()
        ih = self.preview_photo.height()
        sample = max(1, int(max(iw / max(cw - 40, 1), ih / max(ch - 40, 1))))
        image = self.preview_photo.subsample(sample, sample)
        self._preview_scaled = image
        self.preview_canvas.create_image(
            cw // 2, ch // 2, image=image, anchor="center", tags="preview"
        )

    def _open_output(self) -> None:
        path = Path(self.output_var.get().strip())
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except OSError as exc:
            messagebox.showerror("Ошибка", str(exc))


def launch_gui() -> None:
    AssetForgeApp().mainloop()
