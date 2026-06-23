"""BayouFinds Windows Cleanup v1.5.0 Tkinter GUI."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import webbrowser
import ctypes
from datetime import datetime
from math import ceil
from pathlib import Path
from tkinter import PhotoImage, Tk, Toplevel, filedialog, messagebox
from tkinter import BOTH, END, LEFT, RIGHT, X, Y
from tkinter import ttk

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


APP_NAME = "BayouFinds Cleanup Assistant"
APP_VERSION = "v1.5.0"
WINDOW_TITLE = f"{APP_NAME} {APP_VERSION}"
PURCHASE_URL = "https://bayoufinds.com/b/y3OJr"
WINDOW_SIZE = "1200x760"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 760
CONTENT_PADDING = 18
SIDEBAR_WIDTH = 260
HEADER_IMAGE_MAX_WIDTH = WINDOW_WIDTH - (CONTENT_PADDING * 2)
HEADER_IMAGE_MAX_HEIGHT = 40
MASCOT_IMAGE_MAX_WIDTH = 170
MASCOT_IMAGE_MAX_HEIGHT = 170
SPLASH_WIDTH = 620
SPLASH_HEIGHT = 360
SPLASH_IMAGE_MAX_WIDTH = 584
SPLASH_IMAGE_MAX_HEIGHT = 292

BG = "#15181c"
SIDEBAR = "#1b1f24"
PANEL = "#242a31"
PANEL_ALT = "#2b323a"
PANEL_SOFT = "#2b323a"
CARD = "#242a31"
CARD_SOFT = "#2b323a"
CARD_BORDER = "#3a434d"
RESULT_BG = "#1b1f24"
CARD_HIGHLIGHT = "#5d8892"
SHADOW = "#101316"
GLOW = "#476b73"
TEXT = "#f2f4f5"
MUTED = "#b8bec5"
ACCENT = "#5d8892"
ACCENT_DARK = "#476b73"
GOLD = "#c6a15b"
PRIMARY = ACCENT
PRIMARY_DARK = ACCENT_DARK
SUCCESS = "#6aa38d"
WARNING = "#d2a15c"
ERROR = "#c86f6f"


ADMIN_ONLY_ACTIONS = {
    "Deep Windows Check",
    "Repair Windows Files",
    "Repair Windows Networking",
}


def find_asset_path(filename: str, base_dir: Path | None = None) -> Path | None:
    candidates: list[Path] = []

    if base_dir:
        candidates.append(base_dir / "assets" / "optimized" / filename)
        candidates.append(base_dir / "assets" / filename)

    candidates.append(Path(__file__).resolve().parents[1] / "assets" / "optimized" / filename)
    candidates.append(Path(__file__).resolve().parents[1] / "assets" / filename)

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "assets" / "optimized" / filename)
        candidates.append(Path(sys.executable).resolve().parent / "assets" / filename)

    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / "assets" / "optimized" / filename)
        candidates.append(Path(bundle_dir) / "assets" / filename)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def fit_photo_image(path: Path, max_width: int, max_height: int, allow_upscale: bool = False):
    if Image and ImageTk:
        try:
            source = Image.open(path)
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            source.thumbnail((max_width, max_height), resample)

            if allow_upscale and source.width < max_width and source.height < max_height:
                scale = min(max_width / max(source.width, 1), max_height / max(source.height, 1))
                target_size = (
                    max(1, int(source.width * scale)),
                    max(1, int(source.height * scale)),
                )
                source = source.resize(target_size, resample)

            return ImageTk.PhotoImage(source)
        except Exception:
            pass

    try:
        image = PhotoImage(file=str(path))
    except Exception:
        return None

    width = max(image.width(), 1)
    height = max(image.height(), 1)
    scale = max(width / max_width, height / max_height, 1)
    factor = max(1, ceil(scale))

    if factor > 1:
        image = image.subsample(factor, factor)

    return image


def center_window(window: Toplevel | Tk, width: int, height: int) -> None:
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max((screen_width - width) // 2, 0)
    y = max((screen_height - height) // 2, 0)
    window.geometry(f"{width}x{height}+{x}+{y}")


def show_splash_screen(root: Tk) -> None:
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TFrame", background=BG)
    style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 22, "bold"))
    style.configure("Subheader.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 12))
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))

    splash = Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg=BG)
    splash.attributes("-topmost", True)
    center_window(splash, SPLASH_WIDTH, SPLASH_HEIGHT)

    container = ttk.Frame(splash, padding=18)
    container.pack(fill=BOTH, expand=True)

    splash_path = find_asset_path("splash.png")
    splash_image = fit_photo_image(
        splash_path,
        SPLASH_IMAGE_MAX_WIDTH,
        SPLASH_IMAGE_MAX_HEIGHT,
        allow_upscale=True,
    ) if splash_path else None

    if splash_image:
        splash.image_cache = [splash_image]
        ttk.Label(container, image=splash_image, background=BG).pack(expand=True, anchor="center")
    else:
        ttk.Label(container, text="BayouFinds", style="Header.TLabel").pack(pady=(70, 8))
        ttk.Label(container, text="Windows Cleanup", style="Subheader.TLabel").pack()

    ttk.Label(container, text=WINDOW_TITLE, style="Muted.TLabel").pack(pady=(14, 0))
    root.after(2400, splash.destroy)
    root.wait_window(splash)


class BayouFindsCleanupGUI:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.root.configure(bg=BG)

        self.base_dir = self._get_base_dir()
        self.script_path = self._find_cleanup_script()
        self.log_folder = Path.home() / "Desktop" / "BayouFinds_Cleanup_Logs"
        self.output_queue: queue.Queue[tuple[str, str | int | None]] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.current_process: subprocess.Popen[str] | None = None
        self.current_action_name: str | None = None
        self.last_license_mode: str | None = None
        self.gui_elevated = self._is_gui_elevated()
        self.license_state = "required"
        self.run_output_lines: list[str] = []
        self.run_started_at: float | None = None
        self.images: list[PhotoImage] = []
        self.buttons: list[ttk.Button] = []
        self.licensed_buttons: list[ttk.Button] = []
        self.sidebar_buttons: dict[str, ttk.Button] = {}
        self.action_page_buttons: list = []

        self._configure_styles()
        self._set_icon()
        self._build_menu()
        self._build_layout()
        self.refresh_license_state()
        self._poll_output_queue()

    def _is_gui_elevated(self) -> bool:
        if os.name != "nt":
            return False

        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _gui_elevated_text(self) -> str:
        if os.name != "nt":
            return "Unknown"
        return "Yes" if self.gui_elevated else "No"

    def _get_base_dir(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[1]

    def _find_cleanup_script(self) -> Path:
        candidates = [
            self.base_dir / "BayouFinds_Windows_Cleanup.ps1",
            Path(__file__).resolve().parents[1] / "BayouFinds_Windows_Cleanup.ps1",
        ]

        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            candidates.append(Path(bundle_dir) / "BayouFinds_Windows_Cleanup.ps1")

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return candidates[0]

    def _asset_path(self, filename: str) -> Path | None:
        return find_asset_path(filename, self.base_dir)

    def _load_image_fit(
        self,
        filename: str,
        max_width: int,
        max_height: int,
        allow_upscale: bool = False,
    ):
        path = self._asset_path(filename)
        if not path:
            return None

        image = fit_photo_image(path, max_width, max_height, allow_upscale=allow_upscale)
        if not image:
            return None

        self.images.append(image)
        return image

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Main.TFrame", background=BG)
        style.configure("Sidebar.TFrame", background=SIDEBAR)
        style.configure("SoftPanel.TFrame", background=PANEL_SOFT)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 24, "bold"))
        style.configure("Subheader.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 11))
        style.configure("SidebarTitle.TLabel", background=SIDEBAR, foreground="#fff7e8", font=("Segoe UI", 15, "bold"))
        style.configure("SidebarMuted.TLabel", background=SIDEBAR, foreground="#b7d6d1", font=("Segoe UI", 9))
        style.configure(
            "CardTitle.TLabel",
            background=CARD,
            foreground=MUTED,
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "CardValue.TLabel",
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Banner.TLabel",
            background=PANEL_ALT,
            foreground=TEXT,
            font=("Segoe UI", 13, "bold"),
            padding=(12, 10),
        )
        style.configure(
            "DashboardTitle.TLabel",
            background=PANEL_SOFT,
            foreground=MUTED,
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "DashboardValue.TLabel",
            background=PANEL_SOFT,
            foreground=TEXT,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Primary.TButton",
            background=PRIMARY,
            foreground="#0b2727",
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 14, "bold"),
            padding=(22, 17),
        )
        style.map(
            "Primary.TButton",
            background=[("active", PRIMARY_DARK), ("disabled", "#47665d")],
            foreground=[("disabled", "#c4d1cd")],
        )
        style.configure(
            "Action.TButton",
            background="#1d595c",
            foreground=TEXT,
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 10, "bold"),
            padding=(14, 10),
        )
        style.map(
            "Action.TButton",
            background=[("active", ACCENT_DARK), ("disabled", "#1d3438")],
            foreground=[("disabled", "#77928e")],
        )
        style.configure(
            "Secondary.TButton",
            background=ACCENT_DARK,
            foreground=TEXT,
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 10),
            padding=(14, 10),
        )
        style.map("Secondary.TButton", background=[("active", ACCENT), ("disabled", CARD)])
        style.configure(
            "Sidebar.TButton",
            background=SIDEBAR,
            foreground="#d8efea",
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 10, "bold"),
            padding=(14, 10),
            anchor="w",
        )
        style.map("Sidebar.TButton", background=[("active", "#16474b"), ("disabled", SIDEBAR)])
        style.configure(
            "SidebarActive.TButton",
            background="#1c6969",
            foreground="#f7fffb",
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 10, "bold"),
            padding=(14, 10),
            anchor="w",
        )
        style.map("SidebarActive.TButton", background=[("active", "#237b79")])

    def _set_icon(self) -> None:
        icon_path = self._asset_path("app_icon.ico")
        if icon_path:
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

    def _build_menu(self) -> None:
        menu = ttk.Frame(self.root)
        self.root.option_add("*tearOff", False)

        tk_menu = __import__("tkinter").Menu(self.root, bg=PANEL, fg=TEXT, activebackground=ACCENT)
        file_menu = __import__("tkinter").Menu(tk_menu, bg=PANEL, fg=TEXT, activebackground=ACCENT)
        help_menu = __import__("tkinter").Menu(tk_menu, bg=PANEL, fg=TEXT, activebackground=ACCENT)

        file_menu.add_command(label="Import License", command=self.import_license)
        file_menu.add_command(label="Activate Cleanup", command=self.purchase_license)
        file_menu.add_command(label="Open Latest Report", command=self.open_latest_report)
        file_menu.add_command(label="Open Reports / Logs", command=self.open_log_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        help_menu.add_command(label="About", command=self.show_about)

        tk_menu.add_cascade(label="File", menu=file_menu)
        tk_menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=tk_menu)
        menu.destroy()

    def _build_layout(self) -> None:
        if ctk is None:
            messagebox.showerror(
                WINDOW_TITLE,
                "CustomTkinter is required to run this version.\n\nInstall it with:\npython -m pip install customtkinter",
            )
            raise SystemExit("customtkinter is required")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root.grid_columnconfigure(0, minsize=SIDEBAR_WIDTH, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self.root, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(
            sidebar,
            text="BayouFinds",
            text_color=TEXT,
            font=("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(24, 0))
        ctk.CTkLabel(
            sidebar,
            text="Cleanup Assistant",
            text_color=MUTED,
            font=("Segoe UI", 11),
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 22))

        nav_items = [
            ("Home", lambda: self._set_view("Home")),
            ("Scan", lambda: self._set_view("Scan")),
            ("Network Health", lambda: self._set_view("Network Health")),
            ("Cleanup", lambda: self._set_view("Cleanup")),
            ("Reports", lambda: self._set_view("Reports")),
            ("License", lambda: self._set_view("License")),
            ("Help", lambda: self._set_view("Help")),
        ]
        self.sidebar_buttons = {}
        for index, (label, command) in enumerate(nav_items, start=2):
            button = ctk.CTkButton(
                sidebar,
                text=label,
                command=command,
                fg_color=SIDEBAR,
                hover_color=CARD_SOFT,
                text_color=TEXT,
                anchor="w",
                corner_radius=14,
                height=42,
                font=("Segoe UI", 11, "bold"),
            )
            button.grid(row=index, column=0, sticky="ew", padx=18, pady=4)
            self.sidebar_buttons[label] = button

        license_panel = self._ctk_card(sidebar, fg_color=CARD, corner_radius=18)
        license_panel.grid(row=9, column=0, sticky="ew", padx=18, pady=(10, 8))
        license_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            license_panel,
            text="License",
            text_color=MUTED,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
        self.license_value_label = ctk.CTkLabel(
            license_panel,
            text="● ACTIVATION REQUIRED",
            text_color=ERROR,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        self.license_value_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 0))
        ctk.CTkLabel(
            license_panel,
            text="Assessment Mode\n\nScan your PC and generate recovery reports.\n\nCleanup actions unlock after activation.",
            text_color=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=190,
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(4, 12))

        self._ctk_button(
            sidebar,
            "Activate Cleanup",
            self.purchase_license,
            row=10,
            pady=(4, 4),
            fg_color=ACCENT_DARK,
            hover_color=ACCENT,
        )
        self._ctk_button(
            sidebar,
            "Import License",
            self.import_license,
            row=11,
            pady=(4, 8),
            fg_color=ACCENT_DARK,
            hover_color=ACCENT,
        )

        reminder = self._ctk_card(sidebar, fg_color=CARD_SOFT, corner_radius=18)
        reminder.grid(row=12, column=0, sticky="ew", padx=18, pady=(0, 18))
        ctk.CTkLabel(
            reminder,
            text="Protected by Default",
            text_color=GOLD,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            reminder,
            text="Personal folders and saved logins stay protected.",
            text_color=MUTED,
            font=("Segoe UI", 9),
            wraplength=190,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 12))

        main = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=24, pady=22)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(4, weight=1)

        header = ctk.CTkFrame(main, fg_color=BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(0, weight=1)
        self.view_title_label = ctk.CTkLabel(
            header,
            text="Welcome to BayouFinds Cleanup Assistant",
            text_color=TEXT,
            font=("Segoe UI", 26, "bold"),
            anchor="w",
        )
        self.view_title_label.grid(row=0, column=0, sticky="ew")
        self.view_subtitle_label = ctk.CTkLabel(
            header,
            text="Scan your PC to find and safely remove unnecessary files.",
            text_color=MUTED,
            font=("Segoe UI", 12),
            anchor="w",
        )
        self.view_subtitle_label.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkLabel(
            header,
            text=APP_VERSION,
            text_color=ACCENT,
            fg_color=CARD_SOFT,
            corner_radius=14,
            width=92,
            height=34,
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=1, rowspan=2, sticky="ne", padx=(18, 0))

        metrics = ctk.CTkFrame(main, fg_color=BG)
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        for column in range(5):
            metrics.grid_columnconfigure(column, weight=1, uniform="metrics")
        self.recoverable_value_label = self._add_ctk_metric(metrics, 0, "Potential Recovery", "Not scanned yet", "Latest scan estimate.")
        self.cleanup_time_value_label = self._add_ctk_metric(metrics, 1, "Estimated Cleanup Time", "Not scanned yet", "Based on potential recovery.")
        self.recovered_run_value_label = self._add_ctk_metric(metrics, 2, "Recovered This Run", "Not run yet", "Cleanup totals appear here.")
        self.total_recovered_value_label = self._add_ctk_metric(metrics, 3, "Total Recovered", "No cleanup yet", "Saved over time on this PC.")
        self.health_score_value_label = self._add_ctk_metric(metrics, 4, "PC Health Score", "Not scanned yet", "Cleanup readiness score.")

        status_bar = self._ctk_card(main, fg_color=CARD_SOFT, corner_radius=20)
        status_bar.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        for column in range(3):
            status_bar.grid_columnconfigure(column, weight=1, uniform="status")
        self.last_scan_value_label = self._add_ctk_status(status_bar, 0, "Last Scan", "Not run yet")
        self.recommendation_value_label = self._add_ctk_status(status_bar, 1, "Recommendation", "Start with Scan My PC")
        self.status_license_value_label = self._add_ctk_status(status_bar, 2, "Activation Status", "● ACTIVATION REQUIRED", ERROR)

        middle = ctk.CTkFrame(main, fg_color=BG)
        middle.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        middle.grid_columnconfigure(0, weight=1, uniform="middle")
        middle.grid_columnconfigure(1, weight=1, uniform="middle")

        self.action_card = self._ctk_card(middle, fg_color=CARD_SOFT, corner_radius=22)
        self.action_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.action_card.grid_columnconfigure(0, weight=1)
        self.action_buttons_frame = ctk.CTkFrame(self.action_card, fg_color="transparent")
        self.action_title_label = ctk.CTkLabel(
            self.action_card,
            text="Start Here",
            text_color=TEXT,
            font=("Segoe UI", 20, "bold"),
            anchor="w",
        )
        self.action_title_label.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 4))
        self.action_body_label = ctk.CTkLabel(
            self.action_card,
            text="Run a safe scan to estimate recoverable space. No files are deleted during a scan.",
            text_color=MUTED,
            font=("Segoe UI", 12),
            anchor="w",
            justify="left",
            wraplength=430,
        )
        self.action_body_label.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 8))
        self.action_status_label = ctk.CTkLabel(
            self.action_card,
            text="Status: Ready",
            text_color=SUCCESS,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        self.action_status_label.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 22))

        top_hogs = self._ctk_card(middle, fg_color=CARD, corner_radius=22)
        top_hogs.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        top_hogs.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            top_hogs,
            text="Top Space Hogs",
            text_color=GOLD,
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 6))
        self.top_hogs_label = ctk.CTkLabel(
            top_hogs,
            text="Run a scan to see the largest contributors.",
            text_color=MUTED,
            font=("Segoe UI", 12),
            anchor="w",
            justify="left",
            wraplength=430,
        )
        self.top_hogs_label.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 22))

        results = self._ctk_card(main, fg_color=CARD_SOFT, corner_radius=22)
        results.grid(row=4, column=0, sticky="nsew")
        results.grid_columnconfigure(0, weight=1)
        results.grid_rowconfigure(2, weight=1)
        header_row = ctk.CTkFrame(results, fg_color="transparent")
        header_row.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 4))
        header_row.grid_columnconfigure(0, weight=1)
        self.result_banner_label = ctk.CTkLabel(
            header_row,
            text="Scan Results",
            text_color=TEXT,
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        )
        self.result_banner_label.grid(row=0, column=0, sticky="ew")
        self._ctk_inline_button(
            header_row,
            "View Technical Details",
            self.view_technical_details,
            row=0,
            column=1,
            width=180,
        )
        self.status_label = ctk.CTkLabel(
            results,
            text="Ready",
            text_color=MUTED,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        self.status_label.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 8))
        self.output = ctk.CTkTextbox(
            results,
            fg_color=RESULT_BG,
            text_color=TEXT,
            border_width=0,
            corner_radius=16,
            wrap="word",
            font=("Segoe UI", 12),
            height=150,
        )
        self.output.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 22))
        self.output.insert(
            "end",
            "No scan has been run yet.\n\nClick Scan in the left sidebar to check for safe temporary files and app caches.",
        )
        self.output.configure(state="disabled")

        self.license_value_label = self.status_license_value_label
        self._set_view("Home")

    def _set_active_nav(self, label: str) -> None:
        for button_label, button in self.sidebar_buttons.items():
            if hasattr(button, "configure"):
                button.configure(fg_color=CARD_SOFT if button_label == label else SIDEBAR)

    def _ctk_card(self, parent, fg_color: str = CARD, corner_radius: int = 18):
        return ctk.CTkFrame(parent, fg_color=fg_color, corner_radius=corner_radius, border_width=1, border_color=CARD_BORDER)

    def _ctk_button(
        self,
        parent,
        text: str,
        command,
        row: int,
        pady,
        fg_color: str = ACCENT_DARK,
        hover_color: str = ACCENT,
        requires_license: bool = False,
    ):
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=TEXT,
            corner_radius=8,
            height=40,
            font=("Segoe UI", 10, "bold"),
        )
        button.grid(row=row, column=0, sticky="ew", padx=18, pady=pady)
        self.buttons.append(button)
        if requires_license:
            self.licensed_buttons.append(button)
        return button

    def _ctk_inline_button(self, parent, text: str, command, row: int, column: int, width: int = 150):
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            fg_color=ACCENT_DARK,
            hover_color=ACCENT,
            text_color=TEXT,
            corner_radius=8,
            height=38,
            font=("Segoe UI", 10, "bold"),
        )
        button.grid(row=row, column=column, sticky="e", padx=(12, 0))
        self.buttons.append(button)
        return button

    def _add_ctk_metric(self, parent, column: int, title: str, value: str, helper: str):
        card = self._ctk_card(parent, fg_color=CARD, corner_radius=20)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0 if column == 4 else 8))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, text_color=MUTED, font=("Segoe UI", 10, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=18, pady=(18, 4)
        )
        value_label = ctk.CTkLabel(card, text=value, text_color=TEXT, font=("Segoe UI", 15, "bold"), anchor="w")
        value_label.grid(row=1, column=0, sticky="ew", padx=18)
        ctk.CTkLabel(card, text=helper, text_color=MUTED, font=("Segoe UI", 9), anchor="w", wraplength=190).grid(
            row=2, column=0, sticky="ew", padx=18, pady=(6, 18)
        )
        return value_label

    def _add_ctk_status(self, parent, column: int, title: str, value: str, color: str = TEXT):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=column, sticky="ew", padx=18, pady=14)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, text_color=MUTED, font=("Segoe UI", 10, "bold"), anchor="w").grid(row=0, column=0, sticky="ew")
        value_label = ctk.CTkLabel(frame, text=value, text_color=color, font=("Segoe UI", 12, "bold"), anchor="w")
        value_label.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        return value_label

    def _set_view(self, view_name: str) -> None:
        self._set_active_nav(view_name)
        subtitles = {
            "Home": "Scan your PC to find and safely remove unnecessary files.",
            "Scan": "Run a safe scan to estimate recoverable space before cleanup.",
            "Network Health": "Check your IP address, connection, router, and website reachability.",
            "Cleanup": "Safe Cleanup unlocks when an active license is installed.",
            "Reports": "Open reports, logs, and technical details when you need them.",
            "License": "Activate cleanup when you are ready to recover space.",
            "Help": "Safety-first cleanup with personal files protected.",
        }
        title = "Welcome to BayouFinds Cleanup Assistant" if view_name == "Home" else view_name
        self.view_title_label.configure(text=title)
        self.view_subtitle_label.configure(text=subtitles.get(view_name, "Scan first, then choose cleanup."))

        self._clear_action_buttons()
        if view_name == "Home":
            self.action_title_label.configure(text="Start Here")
            self.action_body_label.configure(
                text="Run a safe scan to estimate recoverable space. No files are deleted during a scan."
            )
            self.action_status_label.configure(text="Status: Ready", text_color=SUCCESS)
            self._set_result_banner("Scan Results", TEXT)
            self._clear_output()
            self._append_output("No scan has been run yet.\n\nClick Scan in the left sidebar to check for safe temporary files and app caches.")
        elif view_name == "Scan":
            self.action_title_label.configure(text="Scan My PC")
            self.action_body_label.configure(
                text="Scan checks safe temporary files and app caches. It does not delete files."
            )
            self.action_status_label.configure(text="Status: Ready to scan", text_color=ACCENT)
            self._add_page_button("Scan My PC", self.scan_my_pc, PRIMARY, PRIMARY_DARK, TEXT)
            self._add_page_button("Browser Health", self.browser_health, ACCENT_DARK, ACCENT, TEXT)
            self._set_result_banner("Scan Results", TEXT)
        elif view_name == "Network Health":
            self.action_title_label.configure(text="Network Health")
            self.action_body_label.configure(
                text="Check your IP address, router, DNS, connection type, and website reachability. Repair actions run only when you choose them."
            )
            self.action_status_label.configure(text="Status: Ready to check", text_color=ACCENT)
            self._add_page_button("Network Health", self.network_health, PRIMARY, PRIMARY_DARK, TEXT)
            self._add_page_button("Refresh Website Addresses", self.refresh_website_addresses, ACCENT_DARK, ACCENT, TEXT)
            self._add_page_button("Get New Network Address", self.get_new_network_address, ACCENT_DARK, ACCENT, TEXT)
            self._add_page_button("Repair Windows Networking", self.repair_windows_networking, ACCENT_DARK, ACCENT, TEXT)
            self._add_page_button("Copy Network Report", self.copy_network_report, ACCENT_DARK, ACCENT, TEXT)
            self._set_result_banner("Network Health", TEXT)
        elif view_name == "Cleanup":
            self.action_title_label.configure(text="Run Safe Cleanup")
            self.action_body_label.configure(
                text="Safe Cleanup removes approved temporary files and app caches only. Personal folders stay protected."
            )
            if self.license_state == "active":
                self.action_status_label.configure(text="Status: Cleanup enabled", text_color=SUCCESS)
            else:
                self.action_status_label.configure(text="Status: Cleanup activation required", text_color=WARNING)
            self._add_page_button("Run Safe Cleanup", self.quick_cleanup, ACCENT_DARK, ACCENT, TEXT, requires_license=True)

        if view_name == "Reports":
            self.action_title_label.configure(text="Reports")
            self.action_body_label.configure(text="Open customer reports or technical logs saved on your Desktop.")
            self.action_status_label.configure(text="Status: Reports available after scan", text_color=ACCENT)
            self._add_page_button("Open Latest Report", self.open_latest_report, ACCENT_DARK, ACCENT, TEXT)
            self._add_page_button("Open Reports / Logs", self.open_log_folder, ACCENT_DARK, ACCENT, TEXT)
            self._set_result_banner("Reports — Open Latest Report or Technical Details", TEXT)
            self._clear_output()
            self._append_output("Reports are saved on your Desktop in BayouFinds_Cleanup_Logs.\n\nUse Open Reports / Logs for raw technical logs, or Open Latest Report for the customer report.\n")
        elif view_name == "License":
            self.refresh_license_state()
            self.action_title_label.configure(text="License")
            self.action_body_label.configure(text="Activate Cleanup or import your license file to unlock Safe Cleanup.")
            self.action_status_label.configure(text="Status: Assessment Mode active", text_color=WARNING)
            self._add_page_button("Activate Cleanup", self.purchase_license, ACCENT_DARK, ACCENT, TEXT)
            self._add_page_button("Import License", self.import_license, ACCENT_DARK, ACCENT, TEXT)
            self._clear_output()
            self._append_output("Cleanup activation\n\nAssessment Mode includes Scan My PC and recovery reports. Active licenses unlock Safe Cleanup and recovery tracking.\n\nUse Activate Cleanup or Import License from the sidebar.\n")
        elif view_name == "Help":
            self.action_title_label.configure(text="Help")
            self.action_body_label.configure(text="BayouFinds protects personal folders by default and does not include registry or driver cleanup.")
            self.action_status_label.configure(text="Status: Safety guardrails active", text_color=SUCCESS)
            self._set_result_banner("Protected by Default", SUCCESS)
            self._clear_output()
            self._append_output("Protected by Default\n\nDocuments, Pictures, Downloads, Desktop, Videos, Music, browser passwords, and saved logins are not cleaned by default.\n\nBayouFinds does not include registry cleaning or driver cleanup.\n")
        self._apply_license_button_state()

    def _clear_action_buttons(self) -> None:
        for button in self.action_page_buttons:
            if button in self.buttons:
                self.buttons.remove(button)
            if button in self.licensed_buttons:
                self.licensed_buttons.remove(button)
        for child in self.action_buttons_frame.winfo_children():
            child.destroy()
        self.action_page_buttons = []
        self.action_buttons_frame.grid_forget()

    def _add_page_button(
        self,
        text: str,
        command,
        fg_color: str,
        hover_color: str,
        text_color: str,
        requires_license: bool = False,
    ):
        self.action_buttons_frame.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 22))
        self.action_buttons_frame.grid_columnconfigure(0, weight=1)
        button = ctk.CTkButton(
            self.action_buttons_frame,
            text=text,
            command=command,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            corner_radius=14,
            height=42,
            font=("Segoe UI", 11, "bold"),
        )
        button.grid(row=len(self.action_buttons_frame.winfo_children()), column=0, sticky="ew", pady=4)
        self.buttons.append(button)
        self.action_page_buttons.append(button)
        if requires_license:
            self.licensed_buttons.append(button)
        return button

    def _add_dashboard_row(self, parent: ttk.Frame, label: str, value: str) -> ttk.Label:
        row = ttk.Frame(parent, style="SoftPanel.TFrame")
        row.pack(fill=X, pady=2)
        ttk.Label(
            row,
            text=f"{label}:",
            style="DashboardTitle.TLabel",
            width=20,
        ).pack(side=LEFT)
        value_label = ttk.Label(
            row,
            text=value,
            style="DashboardValue.TLabel",
        )
        value_label.pack(side=LEFT, fill=X, expand=True)
        return value_label

    def _configure_text(self, widget, text: str | None = None, foreground: str | None = None) -> None:
        options = {}
        if text is not None:
            options["text"] = text
        if foreground is not None:
            try:
                widget.configure(**options, text_color=foreground)
                return
            except Exception:
                options["foreground"] = foreground
        widget.configure(**options)

    def _set_dashboard_value(self, label, value: str, foreground: str = TEXT) -> None:
        self._configure_text(label, value, foreground)

    def _set_result_banner(self, text: str, foreground: str = TEXT) -> None:
        self._configure_text(self.result_banner_label, text, foreground)

    def _sync_license_labels(self) -> None:
        if self.license_state == "active":
            text = "● ACTIVE"
            color = SUCCESS
        elif self.license_state == "trial":
            text = "● TRIAL MODE"
            color = WARNING
        else:
            text = "● ACTIVATION REQUIRED"
            color = ERROR

        if hasattr(self, "license_value_label"):
            self._configure_text(self.license_value_label, text, color)
        if hasattr(self, "status_license_value_label"):
            self._configure_text(self.status_license_value_label, text, color)

    def refresh_license_state(self) -> None:
        state, detail = self._read_local_license_state()
        self.license_state = state

        if state == "active":
            self._sync_license_labels()
            self._set_dashboard_value(self.recommendation_value_label, "Scan, then run cleanup", TEXT)
        elif state == "trial":
            self._sync_license_labels()
            self._set_dashboard_value(
                self.recommendation_value_label,
                "Activate Cleanup to recover space",
                WARNING,
            )
        else:
            self._sync_license_labels()
            self._set_dashboard_value(
                self.recommendation_value_label,
                "Activate Cleanup or import a license",
                WARNING,
            )

        self._apply_license_button_state()
        if detail:
            self._configure_text(self.status_label, detail, MUTED if state != "active" else SUCCESS)

    def _read_local_license_state(self) -> tuple[str, str]:
        candidates = [
            (Path.home() / ".bayoufinds" / "license.json", "json"),
            (Path.home() / ".bayoufinds" / "license.key", "legacy-key"),
        ]

        for path, license_format in candidates:
            if not path.exists():
                continue

            if license_format == "legacy-key":
                return "active", "Legacy license found"

            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return "required", "License needs attention"

            product = str(data.get("product") or data.get("product_id") or data.get("app") or "").lower()
            if product and product != "bayoufinds-windows-cleanup" and "cleanup" not in product:
                return "required", "License product mismatch"

            mode = str(data.get("mode") or data.get("license_mode") or "Licensed").strip().lower()
            expires_at = data.get("expiresAt") or data.get("expires_at") or data.get("expires") or data.get("expiration")
            if expires_at and self._is_expired(str(expires_at)):
                return "required", "License expired"

            if mode in {"licensed", "active", "paid"}:
                return "active", "Active license found"
            if mode == "trial":
                return "trial", "Trial license found"
            return "required", "License required"

        return "required", "No license found"

    def _is_expired(self, expires_at: str) -> bool:
        normalized = expires_at.replace("Z", "+00:00")
        try:
            expires_on = datetime.fromisoformat(normalized)
            if expires_on.tzinfo:
                return expires_on < datetime.now().astimezone()
            return expires_on < datetime.now()
        except ValueError:
            pass

        for date_format in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(expires_at, date_format) < datetime.now()
            except ValueError:
                continue
        return True

    def _apply_license_button_state(self) -> None:
        state = "normal" if self.license_state == "active" else "disabled"
        for button in self.licensed_buttons:
            button.configure(state=state)

    def _has_active_license(self) -> bool:
        self.refresh_license_state()
        return self.license_state == "active"

    def purchase_license(self) -> None:
        webbrowser.open(PURCHASE_URL)

    def _show_license_required_prompt(self) -> None:
        prompt = Toplevel(self.root)
        prompt.title("Cleanup Activation Required")
        prompt.geometry("500x260")
        prompt.configure(bg=BG)
        prompt.resizable(False, False)
        prompt.transient(self.root)
        prompt.grab_set()

        frame = ttk.Frame(prompt, padding=22)
        frame.pack(fill=BOTH, expand=True)
        ttk.Label(frame, text="Cleanup Activation Required", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Cleanup Activation Required. Assessment Mode includes scans and recovery reports. "
                "Activate Cleanup to recover space."
            ),
            style="TLabel",
            wraplength=440,
        ).pack(anchor="w", pady=(10, 18))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=X)
        ttk.Button(
            buttons,
            text="Activate Cleanup",
            style="Action.TButton",
            command=lambda: (prompt.destroy(), self.purchase_license()),
        ).pack(side=LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Import License",
            style="Secondary.TButton",
            command=lambda: (prompt.destroy(), self.import_license()),
        ).pack(side=LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Not Now",
            style="Secondary.TButton",
            command=prompt.destroy,
        ).pack(side=RIGHT)

    def _show_admin_required_prompt(self) -> None:
        prompt = Toplevel(self.root)
        prompt.title("Administrator Required")
        prompt.geometry("460x210")
        prompt.configure(bg=BG)
        prompt.resizable(False, False)
        prompt.transient(self.root)
        prompt.grab_set()

        frame = ttk.Frame(prompt, padding=22)
        frame.pack(fill=BOTH, expand=True)
        ttk.Label(frame, text="Administrator Required", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="This action requires Administrator access.",
            style="TLabel",
            wraplength=400,
        ).pack(anchor="w", pady=(12, 22))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=X)
        ttk.Button(
            buttons,
            text="Restart as Administrator",
            style="Action.TButton",
            command=lambda: (prompt.destroy(), self.restart_as_administrator()),
        ).pack(side=LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Cancel",
            style="Secondary.TButton",
            command=prompt.destroy,
        ).pack(side=RIGHT)

    def restart_as_administrator(self) -> None:
        if os.name != "nt":
            messagebox.showinfo(WINDOW_TITLE, "Administrator restart is available on Windows.")
            return

        if getattr(sys, "frozen", False):
            executable = sys.executable
            parameters = " ".join(f'"{arg}"' for arg in sys.argv[1:])
        else:
            executable = sys.executable
            script = Path(__file__).resolve()
            parameters = " ".join([f'"{script}"', *[f'"{arg}"' for arg in sys.argv[1:]]])

        try:
            result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, parameters, None, 1)
        except Exception as exc:
            messagebox.showerror(WINDOW_TITLE, f"Could not restart as Administrator.\n\n{exc}")
            return

        if int(result) <= 32:
            messagebox.showerror(WINDOW_TITLE, "Could not restart as Administrator.")
            return

        self.root.destroy()

    def _ensure_admin_for_action(self, action_name: str) -> bool:
        self.gui_elevated = self._is_gui_elevated()
        if action_name not in ADMIN_ONLY_ACTIONS or self.gui_elevated:
            return True

        self._show_admin_required_prompt()
        return False

    def import_license(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select BayouFinds license.json",
            filetypes=[("BayouFinds license", "license.json"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected:
            return

        source = Path(selected)
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except Exception as exc:
            messagebox.showerror(
                WINDOW_TITLE,
                f"Could not read this license file.\n\n{exc}",
            )
            return

        product = str(data.get("product") or data.get("product_id") or data.get("app") or "").lower()
        customer = data.get("customer") or data.get("customer_name") or data.get("name") or "Customer"
        expires = data.get("expires") or data.get("expires_at") or data.get("expiration") or "Not listed"

        if product and "cleanup" not in product and "bayoufinds-windows-cleanup" not in product:
            if not messagebox.askyesno(
                WINDOW_TITLE,
                "This license does not appear to be for BayouFinds Cleanup Assistant.\n\nImport it anyway?",
            ):
                return

        license_dir = Path.home() / ".bayoufinds"
        license_dir.mkdir(parents=True, exist_ok=True)
        destination = license_dir / "license.json"

        try:
            shutil.copy2(source, destination)
        except Exception as exc:
            messagebox.showerror(
                WINDOW_TITLE,
                f"Could not install the license file.\n\n{exc}",
            )
            return

        self._append_output(
            f"License imported successfully.\nInstalled to: {destination}\nCustomer: {customer}\nExpires: {expires}\n\n"
        )
        self._configure_text(self.status_label, "License imported", SUCCESS)
        self.refresh_license_state()
        messagebox.showinfo(
            WINDOW_TITLE,
            f"License imported successfully.\n\nCustomer: {customer}\nExpires: {expires}\n\nYou can now click License Status to verify activation.",
        )

    def quick_cleanup(self) -> None:
        self._set_active_nav("Cleanup")
        if not self._has_active_license():
            self._show_license_required_prompt()
            return

        if not messagebox.askyesno(
            "Run Safe Cleanup",
            "Run safe cleanup now?\n\nThis cleans safe temporary files and approved app caches only.\nIt will not delete your Documents, Pictures, Desktop, Videos, Music, Downloads, browser passwords, cookies, history, or browser data."
        ):
            return
        self.run_cleanup("Run Safe Cleanup", ["-NoMenu", "-Mode", "SafeCleanup"])

    def deep_cleanup(self) -> None:
        if not self._has_active_license():
            self._show_license_required_prompt()
            return
        if not self._ensure_admin_for_action("Deep Windows Check"):
            return

        if not messagebox.askyesno(
            "Deep Windows Check",
            "Deep Windows Check may take longer because it runs additional Windows file checks.\n\nIt still uses the safe cleanup engine. Continue?"
        ):
            return
        self.run_cleanup("Deep Windows Check", ["-NoMenu", "-Mode", "SafeCleanup", "-SkipSFC:$false"])

    def scan_my_pc(self) -> None:
        self._set_active_nav("Scan")
        self.run_cleanup("Scan My PC", ["-NoMenu", "-Mode", "Preview"])

    def browser_health(self) -> None:
        self._set_active_nav("Scan")
        self.run_cleanup("Browser Health", ["-NoMenu", "-Mode", "BrowserHealth"])

    def network_health(self) -> None:
        self._set_active_nav("Network Health")
        self.run_cleanup("Network Health", ["-NoMenu", "-Mode", "NetworkHealth"])

    def refresh_website_addresses(self) -> None:
        self._set_active_nav("Network Health")
        if not messagebox.askyesno(
            "Refresh Website Addresses",
            "Refresh Website Addresses clears Windows saved website lookup results.\n\nThis can help when websites do not open after a router, modem, or DNS change.\n\nRun this repair now?",
        ):
            return
        self.run_cleanup("Refresh Website Addresses", ["-NoMenu", "-Mode", "FlushDns"])

    def get_new_network_address(self) -> None:
        self._set_active_nav("Network Health")
        if not messagebox.askyesno(
            "Get New Network Address",
            "Get New Network Address asks your router for a network address again.\n\nYour connection may briefly reconnect. Your router may assign the same address again, which is normal.\n\nRun this repair now?",
        ):
            return
        self.run_cleanup("Get New Network Address", ["-NoMenu", "-Mode", "RenewIp"])

    def repair_windows_networking(self) -> None:
        self._set_active_nav("Network Health")
        if not self._ensure_admin_for_action("Repair Windows Networking"):
            return
        if not messagebox.askyesno(
            "Repair Windows Networking",
            "Repair Windows Networking resets Winsock and the Windows IP network stack.\n\nA restart may be needed after this repair. It does not remove adapters, drivers, VPN clients, printers, or startup entries.\n\nRun this repair now?",
        ):
            return
        self.run_cleanup("Repair Windows Networking", ["-NoMenu", "-Mode", "ResetNetwork"])

    def copy_network_report(self) -> None:
        report = self._load_latest_json_report() or {}
        network = report.get("NetworkHealth") or {}
        first_aid = report.get("NetworkFirstAid") or []
        if not network and not first_aid:
            messagebox.showinfo(
                WINDOW_TITLE,
                "No network report was found yet.\n\nClick Network Health first, then use Copy Network Report.",
            )
            return

        text = self._format_network_report_for_clipboard(network, first_aid)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._set_result_banner("Network report copied", SUCCESS)
        self._append_output("\nNetwork report copied to the clipboard.\n")

    def repair_windows_files(self) -> None:
        if not self._has_active_license():
            self._show_license_required_prompt()
            return
        if not self._ensure_admin_for_action("Repair Windows Files"):
            return

        self.run_cleanup("Repair Windows Files", ["-NoMenu", "-Mode", "SafeCleanup", "-SkipSFC:$false"])

    def license_status(self) -> None:
        self._set_active_nav("License")
        self.run_cleanup("License Status", ["-NoMenu", "-Mode", "LicenseCheck"])

    def run_cleanup(self, action_name: str, args: list[str]) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo(WINDOW_TITLE, "Another action is already running.")
            return
        if not self._ensure_admin_for_action(action_name):
            return

        if not self.script_path.exists():
            messagebox.showerror(
                WINDOW_TITLE,
                f"Cleanup script was not found:\n{self.script_path}",
            )
            return

        self._set_running(True)
        self.current_action_name = action_name
        self.run_output_lines = []
        self.run_started_at = datetime.now().timestamp()
        self._set_result_banner(f"{action_name} is running...", ACCENT)
        self._update_dashboard_for_start(action_name)
        self._clear_output()
        self._append_output(f"{action_name} is running...\n\n")
        self._append_output(f"GUI process elevated: {self._gui_elevated_text()}\n")
        self._append_output("This panel will show a plain-English breakdown when the task finishes.\n")
        self._append_output(f"Reports folder: {self.log_folder}\n\n")

        self.worker_thread = threading.Thread(
            target=self._run_subprocess,
            args=(action_name, args),
            daemon=True,
        )
        self.worker_thread.start()

    def _run_subprocess(self, action_name: str, args: list[str]) -> None:
        command = self._build_powershell_command(args)

        try:
            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=str(self.base_dir),
                creationflags=self._creation_flags(),
                startupinfo=self._startup_info(),
            )

            assert self.current_process.stdout is not None
            for line in self.current_process.stdout:
                self.output_queue.put(("line", line))

            exit_code = self.current_process.wait()
            self.output_queue.put(("done", exit_code))
        except Exception as exc:
            self.output_queue.put(("line", f"ERROR: {exc}\n"))
            self.output_queue.put(("done", 1))
        finally:
            self.current_process = None

    def _get_powershell_executable(self) -> str:
        if os.name == "nt":
            return "powershell.exe"
        return "pwsh"

    def _build_powershell_command(self, args: list[str]) -> list[str]:
        command = [
            self._get_powershell_executable(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
        ]

        if os.name == "nt":
            command.extend(["-WindowStyle", "Hidden"])

        command.extend(["-File", str(self.script_path), "-GuiElevated", self._gui_elevated_text(), *args])
        return command

    def _creation_flags(self) -> int:
        if os.name == "nt":
            return subprocess.CREATE_NO_WINDOW
        return 0

    def _startup_info(self):
        if os.name != "nt":
            return None

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        return startupinfo

    def _poll_output_queue(self) -> None:
        try:
            while True:
                event, payload = self.output_queue.get_nowait()
                if event == "line":
                    line = str(payload)
                    self.run_output_lines.append(line)
                    self._capture_license_mode(line)
                elif event == "done":
                    self._handle_done(int(payload or 0))
        except queue.Empty:
            pass

        self.root.after(100, self._poll_output_queue)

    def _handle_done(self, exit_code: int) -> None:
        action_name = self.current_action_name
        self.current_action_name = None
        self._set_running(False)
        self._show_structured_breakdown(action_name, exit_code)
        self.run_started_at = None
        self._update_dashboard_for_done(action_name, exit_code)

        if exit_code == 0:
            self._configure_text(self.status_label, "Completed successfully", SUCCESS)
            messagebox.showinfo(
                WINDOW_TITLE,
                "Task completed successfully.\n\nReview the on-screen results or click Open Latest Report before running additional actions.\n\nReports are saved on your Desktop in:\nBayouFinds_Cleanup_Logs",
            )
        else:
            self._configure_text(self.status_label, "Completed with errors", ERROR)
            messagebox.showerror(
                WINDOW_TITLE,
                f"Task finished with errors.\n\nExit code: {exit_code}\n\nOpen the log folder and review the report before running cleanup again.",
            )

    def _set_running(self, running: bool) -> None:
        for button in self.buttons:
            button.configure(state="disabled" if running else "normal")

        if not running:
            self._apply_license_button_state()

        if running:
            self._configure_text(self.status_label, "Running...", ACCENT)
        else:
            self._configure_text(self.status_label, "Ready", MUTED)

    def _update_dashboard_for_start(self, action_name: str) -> None:
        if action_name == "Scan My PC":
            self._set_dashboard_value(self.last_scan_value_label, "Running now", ACCENT)
            self._set_dashboard_value(self.recoverable_value_label, "Checking...", ACCENT)
            self._set_dashboard_value(self.cleanup_time_value_label, "Estimating...", ACCENT)
            self._set_dashboard_value(self.recovered_run_value_label, "Not run yet", MUTED)
            self._set_dashboard_value(self.recommendation_value_label, "Wait for scan results", TEXT)
            self._configure_text(self.top_hogs_label, "Scanning for largest contributors...", MUTED)
        elif action_name in {"Browser Health", "Network Health"}:
            self._set_dashboard_value(self.last_scan_value_label, "Running now", ACCENT)
            self._set_dashboard_value(self.recommendation_value_label, "Review the report when finished", TEXT)
        elif action_name in {"Refresh Website Addresses", "Get New Network Address", "Repair Windows Networking"}:
            self._set_dashboard_value(self.recommendation_value_label, "Network repair running", ACCENT)
        elif action_name == "Run Safe Cleanup":
            self._set_dashboard_value(self.recovered_run_value_label, "Cleaning...", ACCENT)
            self._set_dashboard_value(self.recommendation_value_label, "Cleaning safe temporary files", TEXT)
        elif action_name == "License Status":
            self._set_dashboard_value(self.license_value_label, "Checking", ACCENT)
            if hasattr(self, "status_license_value_label"):
                self._set_dashboard_value(self.status_license_value_label, "Checking", ACCENT)
            self.last_license_mode = None

    def _update_dashboard_for_done(self, action_name: str | None, exit_code: int) -> None:
        now = datetime.now().strftime("%I:%M %p").lstrip("0")
        if action_name == "Scan My PC":
            if exit_code == 0:
                self._set_dashboard_value(self.last_scan_value_label, f"Completed at {now}", SUCCESS)
                self._set_dashboard_value(
                    self.recommendation_value_label,
                    "Review results, then run cleanup",
                    TEXT,
                )
            else:
                self._set_dashboard_value(self.last_scan_value_label, "Needs attention", ERROR)
                self._set_dashboard_value(self.recommendation_value_label, "Open the report before cleanup", WARNING)
        elif action_name in {"Browser Health", "Network Health"}:
            if exit_code == 0:
                self._set_dashboard_value(self.last_scan_value_label, f"Completed at {now}", SUCCESS)
                self._set_dashboard_value(self.recommendation_value_label, "Review the health report", TEXT)
            else:
                self._set_dashboard_value(self.last_scan_value_label, "Needs attention", ERROR)
                self._set_dashboard_value(self.recommendation_value_label, "Open the report", WARNING)
        elif action_name in {"Refresh Website Addresses", "Get New Network Address", "Repair Windows Networking"}:
            if exit_code == 0:
                self._set_dashboard_value(self.recommendation_value_label, "Network First Aid complete", SUCCESS)
            else:
                self._set_dashboard_value(self.recommendation_value_label, "Review Network First Aid report", WARNING)
        elif action_name == "Run Safe Cleanup":
            if exit_code == 0:
                self._set_dashboard_value(self.recommendation_value_label, "Cleanup complete", SUCCESS)
            else:
                self._set_dashboard_value(self.recommendation_value_label, "Review the report", WARNING)
        elif action_name == "License Status":
            if exit_code == 0 and self.last_license_mode == "licensed":
                self.license_state = "active"
            elif exit_code == 0 and self.last_license_mode == "trial":
                self.license_state = "trial"
            else:
                self.license_state = "required"
            self._sync_license_labels()
            self._apply_license_button_state()

    def _show_structured_breakdown(self, action_name: str | None, exit_code: int) -> None:
        report = self._load_latest_json_report()
        stats = self._load_cleanup_stats()
        self._clear_output()

        if report:
            if report.get("RunMode") == "LicenseCheck":
                self._append_output(self._format_license_breakdown(report, exit_code))
                return
            if report.get("RunMode") == "BrowserHealth":
                self._append_output(self._format_browser_health_breakdown(report, exit_code))
                return
            if report.get("RunMode") == "NetworkHealth":
                self._append_output(self._format_network_health_breakdown(report, exit_code))
                return
            if report.get("RunMode") in {"FlushDns", "RenewIp", "ResetNetwork"}:
                self._append_output(self._format_network_first_aid_breakdown(report, exit_code))
                return
            self._update_metrics_from_report(report, stats)
            self._append_output(self._format_cleanup_breakdown(report, action_name, exit_code))
            return

        self._append_output(f"{action_name or 'Task'} finished with exit code {exit_code}.\n\n")
        self._set_result_banner(
            f"{action_name or 'Task'} finished with errors" if exit_code else f"{action_name or 'Task'} complete",
            ERROR if exit_code else SUCCESS,
        )
        self._append_output("A structured report was not found yet. Open the reports folder to review the log.\n\n")
        if self.run_output_lines:
            self._append_output("Recent messages:\n")
            for line in self.run_output_lines[-12:]:
                self._append_output(f"- {line.strip()}\n")

    def _load_latest_json_report(self) -> dict | None:
        report_path = self._find_latest_json_report(min_mtime=self.run_started_at)
        if not report_path:
            return None
        return self._load_json_file(report_path)

    def _load_cleanup_stats(self) -> dict | None:
        stats_path = self.log_folder / "cleanup_stats.json"
        if not stats_path.exists():
            return None
        return self._load_json_file(stats_path)

    def _load_json_file(self, path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _update_metrics_from_report(self, report: dict, stats: dict | None) -> None:
        statistics = report.get("Statistics") or {}
        categories = report.get("CleanupCategories") or []
        recoverable = int(statistics.get("RecoverableBytes") or 0)
        recovered = int(statistics.get("RecoveredBytes") or 0)
        total_recovered = int(statistics.get("TotalRecoveredBytes") or 0)
        health_score = int(statistics.get("PCHealthScore") or 100)

        if stats:
            total_recovered = int(stats.get("TotalRecoveredBytes") or total_recovered)
            health_score = int(stats.get("PCHealthScore") or health_score)

        self._set_dashboard_value(self.recoverable_value_label, self._format_bytes(recoverable), TEXT)
        self._set_dashboard_value(self.cleanup_time_value_label, self._cleanup_time_estimate(recoverable), GOLD)
        if report.get("RunMode") == "Preview":
            files_identified = sum(int(category.get("EstimatedFiles") or 0) for category in categories if isinstance(category, dict))
            self._set_dashboard_value(self.recovered_run_value_label, f"{files_identified} items found", SUCCESS)
        else:
            self._set_dashboard_value(self.recovered_run_value_label, self._format_bytes(recovered), SUCCESS)
        self._set_dashboard_value(self.total_recovered_value_label, self._format_bytes(total_recovered), SUCCESS)
        self._set_dashboard_value(self.health_score_value_label, f"{health_score}/100", self._health_color(health_score))
        self._update_top_hogs(categories)

    def _format_cleanup_breakdown(self, report: dict, action_name: str | None, exit_code: int) -> str:
        statistics = report.get("Statistics") or {}
        categories = report.get("CleanupCategories") or []
        run_mode = report.get("RunMode") or action_name or "Cleanup"
        recoverable = int(statistics.get("RecoverableBytes") or 0)
        recovered = int(statistics.get("RecoveredBytes") or 0)
        total_recovered = int(statistics.get("TotalRecoveredBytes") or 0)
        health_score = int(statistics.get("PCHealthScore") or 100)
        is_preview = run_mode == "Preview" or action_name == "Scan My PC"
        banner = (
            f"Scan Complete — Potential Recovery: {self._format_gb(recoverable)}"
            if is_preview
            else f"Cleanup Complete — Space Recovered: {self._format_gb(recovered)}"
        )
        self._set_result_banner(banner, SUCCESS if exit_code == 0 else ERROR)
        lines = [
            banner,
            f"Status: {'Completed successfully' if exit_code == 0 else 'Needs attention'}",
            "",
            "Dashboard metrics",
            f"Potential Recovery: {self._format_bytes(recoverable)}",
            f"Estimated Cleanup Time: {self._cleanup_time_estimate(recoverable)}",
            f"Recovered This Run: {self._format_bytes(recovered)}",
            f"Total Recovered: {self._format_bytes(total_recovered)}",
            f"PC Health Score: {health_score}/100",
            "",
            "Top Space Hogs",
            *self._top_space_hog_lines(categories),
            "",
            "Cleanup breakdown",
        ]

        grouped = self._group_cleanup_categories(categories)
        metric_key = "estimated" if is_preview else "recovered"
        for group_name in [
            "Windows Temp",
            "Browser Cache",
            "Discord Cache",
            "Teams Cache",
            "Slack Cache",
            "Zoom Cache",
            "Recycle Bin",
        ]:
            group = grouped[group_name]
            value = self._format_bytes(group[metric_key])
            if group["notes"]:
                lines.append(f"- {group_name}: {value} ({'; '.join(group['notes'])})")
            else:
                lines.append(f"- {group_name}: {value}")

        total = recoverable if is_preview else recovered
        lines.append(f"- Total: {self._format_bytes(total)}")

        paths = report.get("Paths") or {}
        files_identified = sum(int(category.get("EstimatedFiles") or 0) for category in categories if isinstance(category, dict))
        lines.extend([
            "",
            f"Items Found: {files_identified}",
            f"Scan Status: {'Complete' if exit_code == 0 else 'Needs attention'}",
            f"Report Path: {paths.get('HtmlReport') or 'Saved in reports folder'}",
            "",
            "Protected by Default",
            "Documents, Pictures, Downloads, Desktop, Videos, Music, and browser passwords are not cleaned by default.",
            "",
            "Safety",
            "Personal folders are protected by default. Registry cleaning and driver cleanup are not included.",
            "",
            f"Report: {paths.get('HtmlReport') or 'Saved in reports folder'}",
            f"Stats: {paths.get('StatsFile') or str(self.log_folder / 'cleanup_stats.json')}",
            "",
        ])
        return "\n".join(lines)

    def _update_top_hogs(self, categories: list) -> None:
        if not hasattr(self, "top_hogs_label"):
            return
        lines = self._top_space_hog_lines(categories)
        text = "\n".join(lines) if lines else "No large contributors found in the latest scan."
        self._configure_text(self.top_hogs_label, text, TEXT)

    def _top_space_hog_lines(self, categories: list) -> list[str]:
        hogs = []
        for category in categories:
            if not isinstance(category, dict):
                continue
            size = int(category.get("EstimatedBytes") or category.get("ActualBytesRemoved") or 0)
            if size <= 0:
                continue
            hogs.append((size, self._space_hog_label(category)))

        hogs.sort(key=lambda item: item[0], reverse=True)
        return [f"- {label}: {self._format_bytes(size)}" for size, label in hogs[:5]]

    def _space_hog_label(self, category: dict) -> str:
        category_id = str(category.get("Id") or "").lower()
        label = str(category.get("Label") or "").strip()
        combined = f"{category_id} {label.lower()}"

        if "chrome" in combined:
            return "Chrome Cache"
        if "edge" in combined:
            return "Edge Cache"
        if "recycle" in combined:
            return "Recycle Bin"
        if "windows_temp" in combined or label.lower() == "windows temp":
            return "Windows Temp"
        if "downloads" in combined:
            return "Downloads"
        return label.title() if label else "Cleanup Item"

    def _cleanup_time_estimate(self, recoverable_bytes: int) -> str:
        one_gb = 1024 ** 3
        if recoverable_bytes < one_gb:
            return "Less than 1 minute"
        if recoverable_bytes <= 5 * one_gb:
            return "1-2 minutes"
        return "2-5 minutes"

    def _format_license_breakdown(self, report: dict, exit_code: int) -> str:
        license_info = report.get("License") or {}
        mode = license_info.get("Mode") or "Not checked"
        message = license_info.get("Message") or "License check complete."
        normalized_mode = str(mode).lower()
        if normalized_mode == "licensed":
            status = "Active"
            color = SUCCESS
        elif normalized_mode == "trial":
            status = "Trial"
            color = WARNING
        else:
            status = "Needs attention"
            color = ERROR
        self._set_result_banner(f"License Status — {status}", color)
        return "\n".join([
            f"License Status: {status}",
            "",
            f"Mode: {mode}",
            f"Message: {message}",
            f"Exit code: {exit_code}",
            "",
            "Cleanup dashboard metrics were not changed by this license check.",
            "",
        ])

    def _format_browser_health_breakdown(self, report: dict, exit_code: int) -> str:
        browsers = report.get("BrowserHealth") or []
        self._set_result_banner("Browser Health complete", SUCCESS if exit_code == 0 else ERROR)
        lines = [
            "Browser Health",
            f"Status: {'Completed successfully' if exit_code == 0 else 'Needs attention'}",
            "",
            "This scan does not collect passwords, cookies, browsing history, or private browser data.",
            "",
        ]

        for browser in browsers:
            if not isinstance(browser, dict):
                continue
            installed = "Installed" if browser.get("Installed") else "Not found"
            extension_count = browser.get("ExtensionCount")
            extension_text = "Unknown" if extension_count is None else str(extension_count)
            lines.extend([
                f"{browser.get('Name') or 'Browser'}: {installed}",
                f"- Version: {browser.get('Version') or 'Unknown'}",
                f"- Default Browser: {browser.get('DefaultBrowser') or 'Unknown'}",
                f"- Cache Estimate: {browser.get('CacheSize') or 'Unknown'}",
                f"- Extensions: {extension_text}",
                f"- Update Status: {browser.get('UpdateStatus') or 'Unknown'}",
                "",
            ])

        paths = report.get("Paths") or {}
        lines.extend([
            f"Report: {paths.get('HtmlReport') or 'Saved in reports folder'}",
            "",
        ])
        return "\n".join(lines)

    def _format_network_health_breakdown(self, report: dict, exit_code: int) -> str:
        network = report.get("NetworkHealth") or {}
        self._set_result_banner("Network Health complete", SUCCESS if exit_code == 0 else ERROR)
        lines = [
            "Network Health",
            f"Status: {'Completed successfully' if exit_code == 0 else 'Needs attention'}",
            "",
            f"Your IP Address: {network.get('YourIPAddress') or 'Unknown'}",
            f"Gateway: {self._join_report_list(network.get('Gateway'))}",
            f"DNS Servers: {self._join_report_list(network.get('DNSServers'))}",
            f"Connection Type: {network.get('ConnectionType') or 'Unknown'}",
            f"Wi-Fi and Ethernet Connected Together: {network.get('WifiAndEthernetConnected')}",
            f"Internet Reachable: {network.get('InternetReachable') or 'Unknown'}",
            f"Gateway Reachable: {network.get('GatewayReachable') or 'Unknown'}",
            "",
            "Active IPv4 Addresses",
        ]

        addresses = network.get("ActiveIPv4Addresses") or []
        if addresses:
            for item in addresses:
                if not isinstance(item, dict):
                    continue
                primary = " (primary)" if item.get("IsPrimary") else ""
                lines.append(f"- {item.get('Address') or 'Unknown'}{primary} - {item.get('ConnectionType') or 'Unknown'}")
        else:
            lines.append("- Unknown")

        vpn_adapters = network.get("VPNAdaptersDetected") or []
        lines.append("")
        if vpn_adapters:
            lines.append("VPN Adapters Detected")
            for adapter in vpn_adapters:
                if isinstance(adapter, dict):
                    lines.append(f"- {adapter.get('Name') or 'Unknown'}")
        else:
            lines.append("VPN Adapters Detected: None obvious")

        paths = report.get("Paths") or {}
        lines.extend([
            "",
            f"Report: {paths.get('HtmlReport') or 'Saved in reports folder'}",
            "",
        ])
        return "\n".join(lines)

    def _format_network_first_aid_breakdown(self, report: dict, exit_code: int) -> str:
        results = report.get("NetworkFirstAid") or []
        self._set_result_banner("Network First Aid complete", SUCCESS if exit_code == 0 else ERROR)
        lines = [
            "Network First Aid",
            f"Status: {'Completed successfully' if exit_code == 0 else 'Needs attention'}",
            "",
        ]

        for result in results:
            if not isinstance(result, dict):
                continue
            lines.extend([
                f"Action: {result.get('Action') or 'Network repair'}",
                f"Result: {result.get('Status') or 'Unknown'}",
                f"Message: {result.get('Message') or 'Finished'}",
                f"Previous IP Address: {result.get('PreviousIPv4') or 'Unknown'}",
                f"Current IP Address: {result.get('CurrentIPv4') or 'Unknown'}",
                f"Gateway: {self._join_report_list(result.get('Gateway'))}",
                f"DNS Servers: {self._join_report_list(result.get('DNSServers'))}",
                "",
            ])

        paths = report.get("Paths") or {}
        lines.extend([
            f"Report: {paths.get('HtmlReport') or 'Saved in reports folder'}",
            "",
        ])
        return "\n".join(lines)

    def _format_network_report_for_clipboard(self, network: dict, first_aid: list) -> str:
        lines = [
            "BayouFinds Network Report",
            "",
            f"Your IP Address: {network.get('YourIPAddress') or 'Unknown'}",
            f"Gateway: {self._join_report_list(network.get('Gateway'))}",
            f"DNS Servers: {self._join_report_list(network.get('DNSServers'))}",
            f"Connection Type: {network.get('ConnectionType') or 'Unknown'}",
            f"Internet Reachable: {network.get('InternetReachable') or 'Unknown'}",
            f"Gateway Reachable: {network.get('GatewayReachable') or 'Unknown'}",
            "",
            "Active IPv4 Addresses:",
        ]
        for item in network.get("ActiveIPv4Addresses") or []:
            if isinstance(item, dict):
                primary = " primary" if item.get("IsPrimary") else ""
                lines.append(f"- {item.get('Address') or 'Unknown'}{primary}")

        if first_aid:
            lines.extend(["", "Network First Aid:"])
            for result in first_aid:
                if isinstance(result, dict):
                    lines.append(f"- {result.get('Action') or 'Action'}: {result.get('Status') or 'Unknown'} - {result.get('Message') or ''}")

        return "\n".join(lines)

    def _join_report_list(self, value) -> str:
        if not value:
            return "Unknown"
        if isinstance(value, list):
            items = [str(item) for item in value if str(item).strip()]
            return ", ".join(items) if items else "Unknown"
        return str(value)

    def _group_cleanup_categories(self, categories: list) -> dict[str, dict]:
        grouped = {
            "Windows Temp": {"estimated": 0, "recovered": 0, "notes": []},
            "Browser Cache": {"estimated": 0, "recovered": 0, "notes": []},
            "Discord Cache": {"estimated": 0, "recovered": 0, "notes": []},
            "Teams Cache": {"estimated": 0, "recovered": 0, "notes": []},
            "Slack Cache": {"estimated": 0, "recovered": 0, "notes": []},
            "Zoom Cache": {"estimated": 0, "recovered": 0, "notes": []},
            "Recycle Bin": {"estimated": 0, "recovered": 0, "notes": []},
        }

        for category in categories:
            if not isinstance(category, dict):
                continue

            group_name = self._category_group_name(category)
            if not group_name:
                continue

            grouped[group_name]["estimated"] += int(category.get("EstimatedBytes") or 0)
            grouped[group_name]["recovered"] += int(category.get("ActualBytesRemoved") or 0)
            reason = category.get("SkippedReason")
            if reason and reason not in grouped[group_name]["notes"]:
                grouped[group_name]["notes"].append(str(reason))

        return grouped

    def _category_group_name(self, category: dict) -> str | None:
        category_id = str(category.get("Id") or "").lower()
        label = str(category.get("Label") or "").lower()
        combined = f"{category_id} {label}"

        if "recycle" in combined:
            return "Recycle Bin"
        if "discord" in combined:
            return "Discord Cache"
        if "teams" in combined:
            return "Teams Cache"
        if "slack" in combined:
            return "Slack Cache"
        if "zoom" in combined:
            return "Zoom Cache"
        if any(token in combined for token in ["edge", "chrome", "browser", "internet", "web cache"]):
            return "Browser Cache"
        if any(token in combined for token in ["temp", "recent"]):
            return "Windows Temp"
        return None

    def _format_bytes(self, value: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        amount = float(max(value, 0))
        unit_index = 0
        while amount >= 1024 and unit_index < len(units) - 1:
            amount /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(amount)} {units[unit_index]}"
        return f"{amount:.1f} {units[unit_index]}"

    def _format_gb(self, value: int) -> str:
        return f"{max(value, 0) / (1024 ** 3):.2f} GB"

    def _health_color(self, score: int) -> str:
        if score >= 85:
            return SUCCESS
        if score >= 70:
            return WARNING
        return ERROR

    def _capture_license_mode(self, line: str) -> None:
        marker = "license mode:"
        lower_line = line.lower()
        if marker not in lower_line:
            return

        mode = lower_line.split(marker, 1)[1].strip().split(" ", 1)[0]
        self.last_license_mode = mode.strip(".")

    def _clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", END)
        self.output.configure(state="disabled")

    def _append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert(END, text)
        self.output.see(END)
        self.output.configure(state="disabled")

    def open_log_folder(self) -> None:
        self.log_folder.mkdir(parents=True, exist_ok=True)

        if os.name == "nt":
            os.startfile(self.log_folder)  # type: ignore[attr-defined]
        else:
            webbrowser.open(self.log_folder.as_uri())

    def open_latest_report(self) -> None:
        latest_report = self._find_latest_report()
        if not latest_report:
            messagebox.showinfo(
                WINDOW_TITLE,
                "No cleanup report was found yet.\n\nClick Scan My PC first, then use Open Latest Report.",
            )
            return

        if os.name == "nt":
            os.startfile(latest_report)  # type: ignore[attr-defined]
        else:
            webbrowser.open(latest_report.as_uri())

    def view_technical_details(self) -> None:
        latest_log = self._find_latest_log()
        if not latest_log:
            self.open_log_folder()
            return

        if os.name == "nt":
            os.startfile(latest_log)  # type: ignore[attr-defined]
        else:
            webbrowser.open(latest_log.as_uri())

    def _find_latest_report(self) -> Path | None:
        if not self.log_folder.exists():
            return None

        reports = sorted(
            self.log_folder.glob("cleanup_report_*.html"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return reports[0] if reports else None

    def _find_latest_log(self) -> Path | None:
        if not self.log_folder.exists():
            return None

        logs = sorted(
            self.log_folder.glob("cleanup_*.log"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return logs[0] if logs else None

    def _find_latest_json_report(self, min_mtime: float | None = None) -> Path | None:
        if not self.log_folder.exists():
            return None

        reports = []
        for path in self.log_folder.glob("cleanup_report_*.json"):
            modified_at = path.stat().st_mtime
            if min_mtime is not None and modified_at < min_mtime - 2:
                continue
            reports.append(path)

        reports.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return reports[0] if reports else None

    def show_about(self) -> None:
        about = Toplevel(self.root)
        about.title(f"About {APP_NAME}")
        about.geometry("460x420")
        about.configure(bg=BG)
        about.resizable(False, False)
        about.transient(self.root)
        about.grab_set()

        frame = ttk.Frame(about, padding=24)
        frame.pack(fill=BOTH, expand=True)

        mascot_image = self._load_image_fit(
            "cleanup_mascot.png",
            MASCOT_IMAGE_MAX_WIDTH,
            MASCOT_IMAGE_MAX_HEIGHT,
        )
        if mascot_image:
            ttk.Label(frame, image=mascot_image, background=BG).pack(anchor="center", pady=(0, 10))

        ttk.Label(frame, text=APP_NAME, style="Header.TLabel").pack(anchor="w")
        ttk.Label(frame, text=APP_VERSION, style="Subheader.TLabel").pack(anchor="w", pady=(6, 12))
        ttk.Label(frame, text="Built by BayouFinds", style="TLabel").pack(anchor="w")
        ttk.Label(frame, text="https://bayoufinds.com", style="Muted.TLabel").pack(anchor="w", pady=(4, 12))
        ttk.Label(
            frame,
            text="A scan-first Windows cleanup and reporting utility for home users.",
            style="TLabel",
            wraplength=390,
        ).pack(anchor="w", pady=(0, 20))

        ttk.Button(frame, text="Close", style="Secondary.TButton", command=about.destroy).pack(anchor="e")


def main() -> None:
    if ctk is None:
        raise SystemExit("customtkinter is required. Install it with: python -m pip install customtkinter")

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    root = ctk.CTk()
    root.withdraw()
    show_splash_screen(root)
    BayouFindsCleanupGUI(root)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
