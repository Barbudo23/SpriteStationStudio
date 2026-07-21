from __future__ import annotations

from tkinter import ttk


COLORS = {
    "bg": "#15181d",
    "panel": "#1d2229",
    "panel_alt": "#242a33",
    "field": "#111419",
    "border": "#343b46",
    "text": "#e7eaf0",
    "muted": "#9aa4b2",
    "accent": "#d18f3f",
    "accent_active": "#eca956",
    "success": "#5bb98c",
    "warning": "#d6a24b",
    "error": "#d06666",
}


def apply_theme(root) -> None:
    root.configure(bg=COLORS["bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", background=COLORS["panel"], foreground=COLORS["text"])
    style.configure("TFrame", background=COLORS["panel"])
    style.configure("Shell.TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("Alt.TFrame", background=COLORS["panel_alt"])
    style.configure("TLabel", background=COLORS["panel"], foreground=COLORS["text"])
    style.configure("Muted.TLabel", foreground=COLORS["muted"])
    style.configure("BridgeOnline.TLabel", foreground="#4ADE80", font=("Segoe UI", 10, "bold"))
    style.configure("BridgeOffline.TLabel", foreground="#F87171", font=("Segoe UI", 10, "bold"))
    style.configure("BridgeChecking.TLabel", foreground="#FBBF24", font=("Segoe UI", 10, "bold"))
    style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
    style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"))
    style.configure("Badge.TLabel", background=COLORS["accent"], foreground="#161616",
                    padding=(7, 3), font=("Segoe UI", 9, "bold"))

    style.configure(
        "TButton",
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        padding=(10, 7),
    )
    style.map(
        "TButton",
        background=[("active", COLORS["border"]), ("pressed", COLORS["field"])],
    )
    style.configure(
        "Primary.TButton",
        background=COLORS["accent"],
        foreground="#18130d",
        bordercolor=COLORS["accent"],
        font=("Segoe UI", 10, "bold"),
        padding=(14, 8),
    )
    style.map("Primary.TButton", background=[("active", COLORS["accent_active"])])

    style.configure(
        "TEntry",
        fieldbackground=COLORS["field"],
        foreground=COLORS["text"],
        insertcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        padding=6,
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["field"],
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        padding=5,
    )
    style.map("TCombobox", fieldbackground=[("readonly", COLORS["field"])])

    style.configure(
        "TNotebook",
        background=COLORS["panel"],
        bordercolor=COLORS["border"],
    )
    style.configure(
        "TNotebook.Tab",
        background=COLORS["panel_alt"],
        foreground=COLORS["muted"],
        padding=(12, 7),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["panel"])],
        foreground=[("selected", COLORS["text"])],
    )

    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=COLORS["field"],
        background=COLORS["accent"],
        bordercolor=COLORS["field"],
    )
