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
from datetime import datetime
from math import ceil
from pathlib import Path
from tkinter import Canvas, Frame, PhotoImage, Tk, Toplevel, filedialog, messagebox
from tkinter import BOTH, END, LEFT, RIGHT, X, Y
from tkinter import scrolledtext, ttk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


APP_NAME = "BayouFinds Cleanup Assistant"
APP_VERSION = "v1.5.0"
WINDOW_TITLE = f"{APP_NAME} {APP_VERSION}"
PURCHASE_URL = "https://bayoufinds.com/b/y3OJr"
WINDOW_SIZE = "1040x700"
WINDOW_WIDTH = 1040
WINDOW_HEIGHT = 700
CONTENT_PADDING = 18
HEADER_IMAGE_MAX_WIDTH = WINDOW_WIDTH - (CONTENT_PADDING * 2)
HEADER_IMAGE_MAX_HEIGHT = 40
MASCOT_IMAGE_MAX_WIDTH = 170
MASCOT_IMAGE_MAX_HEIGHT = 170
SPLASH_WIDTH = 620
SPLASH_HEIGHT = 360
SPLASH_IMAGE_MAX_WIDTH = 584
SPLASH_IMAGE_MAX_HEIGHT = 292

BG = "#071b1d"
SIDEBAR = "#0a2528"
PANEL = "#0d2a2e"
PANEL_ALT = "#153c40"
PANEL_SOFT = "#12353a"
CARD = "#103338"
CARD_SOFT = "#143d42"
CARD_BORDER = "#2d6f70"
CARD_HIGHLIGHT = "#5bd4c3"
SHADOW = "#031012"
GLOW = "#1e6967"
TEXT = "#f5fbf8"
MUTED = "#a8c7c2"
ACCENT = "#6fdad0"
ACCENT_DARK = "#2ea6a0"
PRIMARY = "#77e0a5"
PRIMARY_DARK = "#4bbf7c"
SUCCESS = "#7ee7a6"
WARNING = "#f1c96b"
ERROR = "#ff7c7c"


def draw_round_rect(canvas: Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> int:
    radius = min(radius, max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2))
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=20, **kwargs)


class GlassCard(Frame):
    def __init__(
        self,
        parent,
        fill: str = CARD,
        border: str = CARD_BORDER,
        bg: str = BG,
        shadow: str = SHADOW,
        glow: bool = False,
        radius: int = 22,
        padding: int = 16,
        min_width: int = 120,
        min_height: int = 90,
    ) -> None:
        super().__init__(parent, bg=bg)
        self.fill = fill
        self.border = CARD_HIGHLIGHT if glow else border
        self.bg = bg
        self.shadow = GLOW if glow else shadow
        self.radius = radius
        self.padding = padding
        self.canvas = Canvas(
            self,
            bg=bg,
            bd=0,
            highlightthickness=0,
            width=min_width,
            height=min_height,
        )
        self.canvas.pack(fill=BOTH, expand=True)
        self.inner = Frame(self.canvas, bg=fill)
        self.window_id = self.canvas.create_window(
            padding + 5,
            padding + 4,
            anchor="nw",
            window=self.inner,
        )
        self.canvas.bind("<Configure>", self._draw)

    def _draw(self, event) -> None:
        width = max(event.width, 20)
        height = max(event.height, 20)
        self.canvas.delete("shape")
        draw_round_rect(
            self.canvas,
            7,
            9,
            width - 2,
            height - 2,
            self.radius,
            fill=self.shadow,
            outline="",
            tags="shape",
        )
        draw_round_rect(
            self.canvas,
            1,
            1,
            width - 8,
            height - 8,
            self.radius,
            fill=self.fill,
            outline=self.border,
            width=1,
            tags="shape",
        )
        draw_round_rect(
            self.canvas,
            6,
            5,
            width - 16,
            max(10, height // 3),
            max(10, self.radius - 8),
            fill="#1b4e52",
            outline="",
            tags="shape",
        )
        self.canvas.tag_lower("shape")
        self.canvas.coords(self.window_id, self.padding + 5, self.padding + 4)
        self.canvas.itemconfigure(
            self.window_id,
            width=max(20, width - (self.padding * 2) - 16),
            height=max(20, height - (self.padding * 2) - 14),
        )


class GlassButton(Frame):
    def __init__(
        self,
        parent,
        text: str,
        command=None,
        width: int = 170,
        height: int = 44,
        fill: str = "#173f44",
        active_fill: str = "#22595e",
        foreground: str = TEXT,
        disabled_fill: str = "#1b3337",
        disabled_foreground: str = "#77928e",
        glow: bool = False,
        radius: int = 18,
        font: tuple = ("Segoe UI", 10, "bold"),
        bg: str = CARD_SOFT,
    ) -> None:
        super().__init__(parent, bg=bg)
        self.text = text
        self.command = command
        self.width = width
        self.height = height
        self.fill = fill
        self.active_fill = active_fill
        self.foreground = foreground
        self.disabled_fill = disabled_fill
        self.disabled_foreground = disabled_foreground
        self.glow = glow
        self.radius = radius
        self.font = font
        self.state = "normal"
        self.is_active = False
        self.canvas = Canvas(
            self,
            width=width,
            height=height,
            bg=bg,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Enter>", lambda _event: self._draw(hover=True))
        self.canvas.bind("<Leave>", lambda _event: self._draw())
        self._draw()

    def _draw(self, hover: bool = False) -> None:
        self.canvas.delete("all")
        disabled = self.state == "disabled"
        fill = self.disabled_fill if disabled else (self.active_fill if hover or self.is_active else self.fill)
        text_color = self.disabled_foreground if disabled else self.foreground
        shadow = GLOW if self.glow or self.is_active else SHADOW
        draw_round_rect(
            self.canvas,
            5,
            7,
            self.width - 1,
            self.height - 1,
            self.radius,
            fill=shadow,
            outline="",
        )
        draw_round_rect(
            self.canvas,
            1,
            1,
            self.width - 6,
            self.height - 7,
            self.radius,
            fill=fill,
            outline=CARD_HIGHLIGHT if self.glow or self.is_active else CARD_BORDER,
            width=1,
        )
        self.canvas.create_text(
            (self.width - 6) // 2,
            (self.height - 6) // 2,
            text=self.text,
            fill=text_color,
            font=self.font,
        )
        self.canvas.configure(cursor="" if disabled else "hand2")

    def _click(self, _event) -> None:
        if self.state == "disabled" or not self.command:
            return
        self.command()

    def configure(self, cnf=None, **kwargs):  # type: ignore[override]
        if cnf:
            kwargs.update(cnf)
        if "state" in kwargs:
            self.state = kwargs.pop("state")
        if "active" in kwargs:
            self.is_active = bool(kwargs.pop("active"))
        if "text" in kwargs:
            self.text = str(kwargs.pop("text"))
        if kwargs:
            super().configure(**kwargs)
        self._draw()

    config = configure


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
        self.license_state = "required"
        self.run_output_lines: list[str] = []
        self.run_started_at: float | None = None
        self.images: list[PhotoImage] = []
        self.buttons: list[ttk.Button] = []
        self.licensed_buttons: list[ttk.Button] = []
        self.sidebar_buttons: dict[str, ttk.Button] = {}

        self._configure_styles()
        self._set_icon()
        self._build_menu()
        self._build_layout()
        self.refresh_license_state()
        self._poll_output_queue()

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
            background="#173f44",
            foreground=TEXT,
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 10),
            padding=(14, 10),
        )
        style.map("Secondary.TButton", background=[("active", "#22595e"), ("disabled", "#172f33")])
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
        file_menu.add_command(label="Purchase License", command=self.purchase_license)
        file_menu.add_command(label="Open Latest Report", command=self.open_latest_report)
        file_menu.add_command(label="Open Reports / Logs", command=self.open_log_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        help_menu.add_command(label="About", command=self.show_about)

        tk_menu.add_cascade(label="File", menu=file_menu)
        tk_menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=tk_menu)
        menu.destroy()

    def _glass_card(
        self,
        parent,
        fill: str = CARD,
        padding: int = 14,
        border: str = CARD_BORDER,
        shadow: str = SHADOW,
        glow: bool = False,
        bg: str = BG,
        min_width: int = 120,
        min_height: int = 90,
    ) -> Frame:
        card = GlassCard(
            parent,
            fill=fill,
            border=border,
            bg=bg,
            shadow=shadow,
            glow=glow,
            padding=padding,
            min_width=min_width,
            min_height=min_height,
        )
        card.inner._glass_outer = card  # type: ignore[attr-defined]
        return card.inner

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, style="Main.TFrame")
        outer.pack(fill=BOTH, expand=True)

        sidebar_panel = GlassCard(
            outer,
            fill=SIDEBAR,
            border="#2c7272",
            bg=BG,
            shadow=GLOW,
            glow=True,
            radius=30,
            padding=12,
            min_width=230,
            min_height=640,
        )
        sidebar_panel.pack(side=LEFT, fill=Y, padx=(18, 0), pady=18)
        sidebar_panel.configure(width=230)
        sidebar_panel.pack_propagate(False)

        nav_inner = Frame(sidebar_panel.inner, bg=SIDEBAR)
        nav_inner.pack(fill=BOTH, expand=True, padx=16, pady=16)

        ttk.Label(nav_inner, text="BayouFinds", style="SidebarTitle.TLabel").pack(anchor="w")
        ttk.Label(nav_inner, text="Cleanup Assistant", style="SidebarMuted.TLabel").pack(anchor="w", pady=(2, 18))

        for label, command in [
            ("Home", lambda: self._set_view("Home")),
            ("Scan", self.scan_my_pc),
            ("Cleanup", self.quick_cleanup),
            ("Reports", self.open_latest_report),
            ("License", self.license_status),
            ("Help", self.show_about),
        ]:
            self._add_sidebar_button(nav_inner, label, command)

        Frame(nav_inner, bg=SIDEBAR).pack(fill=BOTH, expand=True)

        license_panel = self._glass_card(nav_inner, fill="#11373b", padding=10, glow=True, bg=SIDEBAR)
        license_panel._glass_outer.pack(fill=X, pady=(0, 12))  # type: ignore[attr-defined]
        ttk.Label(
            license_panel,
            text="License",
            background="#11373b",
            foreground=MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        self.license_value_label = ttk.Label(
            license_panel,
            text="● LICENSE REQUIRED",
            background="#11373b",
            foreground=ERROR,
            font=("Segoe UI", 12, "bold"),
        )
        self.license_value_label.pack(anchor="w", pady=(2, 0))
        ttk.Label(
            license_panel,
            text="Trial: scan and reports only",
            background="#11373b",
            foreground=MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(2, 0))

        self._add_sidebar_button(nav_inner, "Purchase License", self.purchase_license)
        self._add_sidebar_button(nav_inner, "Import License", self.import_license)

        main = ttk.Frame(outer, style="Main.TFrame", padding=(22, 18, 18, 18))
        main.pack(side=RIGHT, fill=BOTH, expand=True)

        header = ttk.Frame(main, style="Main.TFrame")
        header.pack(fill=X)

        header_text = ttk.Frame(header, style="Main.TFrame")
        header_text.pack(side=LEFT, fill=X, expand=True)
        self.view_title_label = ttk.Label(header_text, text="Home", style="Header.TLabel")
        self.view_title_label.pack(anchor="w")
        self.view_subtitle_label = ttk.Label(
            header_text,
            text="A calm, scan-first way to care for your PC.",
            style="Subheader.TLabel",
        )
        self.view_subtitle_label.pack(anchor="w", pady=(2, 0))

        header_image = self._load_image_fit(
            "header_banner.png",
            180,
            HEADER_IMAGE_MAX_HEIGHT,
            allow_upscale=False,
        )
        if header_image:
            ttk.Label(header, image=header_image, background=BG).pack(side=RIGHT, padx=(16, 0))

        dashboard = ttk.Frame(main, style="Main.TFrame")
        dashboard.pack(fill=X, pady=(16, 12))

        self.recoverable_value_label = self._add_metric_card(
            dashboard,
            "◌",
            "Recoverable Space",
            "Not scanned yet",
            "Scan first to estimate safe space.",
            0,
            0,
        )
        self.recovered_run_value_label = self._add_metric_card(
            dashboard,
            "✓",
            "Recovered This Run",
            "Not run yet",
            "Cleanup totals appear here.",
            0,
            1,
        )
        self.total_recovered_value_label = self._add_metric_card(
            dashboard,
            "↟",
            "Total Recovered",
            "No cleanup yet",
            "Saved over time on this PC.",
            0,
            2,
        )
        self.health_score_value_label = self._add_metric_card(
            dashboard,
            "♡",
            "PC Health",
            "Not scanned yet",
            "A simple cleanup readiness score.",
            0,
            3,
        )
        for column in range(4):
            dashboard.columnconfigure(column, weight=1)

        action_row = self._glass_card(main, fill=CARD_SOFT, padding=16, glow=True)
        action_row._glass_outer.pack(fill=X, pady=(0, 12))  # type: ignore[attr-defined]
        action_text = Frame(action_row, bg=CARD_SOFT)
        action_text.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 16))
        ttk.Label(
            action_text,
            text="Start with a safe scan",
            background=CARD_SOFT,
            foreground=TEXT,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            action_text,
            text="Scan My PC checks for safe cleanup space. It does not delete files.",
            background=CARD_SOFT,
            foreground=MUTED,
            font=("Segoe UI", 10),
            wraplength=420,
        ).pack(anchor="w", pady=(4, 0))
        action_buttons = Frame(action_row, bg=CARD_SOFT)
        action_buttons.pack(side=RIGHT, fill=X)
        self._add_primary_button(action_buttons, "Scan My PC", self.scan_my_pc)
        self._add_action_button(action_buttons, "Run Safe Cleanup", self.quick_cleanup, requires_license=True)
        small_buttons = Frame(action_buttons, bg=CARD_SOFT)
        small_buttons.pack(fill=X)
        self._add_secondary_button(small_buttons, "Purchase License", self.purchase_license, side=LEFT)
        self._add_secondary_button(small_buttons, "Import License", self.import_license, side=RIGHT)

        trust_row = ttk.Frame(main, style="Main.TFrame")
        trust_row.pack(fill=X, pady=(0, 12))

        protected = self._glass_card(trust_row, fill=CARD, padding=14)
        protected._glass_outer.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))  # type: ignore[attr-defined]
        ttk.Label(
            protected,
            text="Protected by Default",
            background=CARD,
            foreground=SUCCESS,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            protected,
            text="✓ Documents    ✓ Pictures    ✓ Downloads    ✓ Desktop\n✓ Videos       ✓ Music       ✓ Browser Passwords\n✓ Saved Logins",
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        guardrails = self._glass_card(trust_row, fill=CARD, padding=14)
        guardrails._glass_outer.pack(side=RIGHT, fill=BOTH, expand=True, padx=(8, 0))  # type: ignore[attr-defined]
        ttk.Label(
            guardrails,
            text="Safe Cleanup Rules",
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            guardrails,
            text="No registry cleaning\nNo driver cleanup\nApps are skipped while running",
            background=CARD,
            foreground=MUTED,
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        self.last_scan_value_label = ttk.Label(
            main,
            text="Last Scan: Not run yet",
            background=BG,
            foreground=MUTED,
            font=("Segoe UI", 9),
        )
        self.last_scan_value_label.pack(anchor="w", pady=(0, 2))
        self.recommendation_value_label = ttk.Label(
            main,
            text="Recommendation: Start with Scan My PC",
            background=BG,
            foreground=TEXT,
            font=("Segoe UI", 9, "bold"),
        )
        self.recommendation_value_label.pack(anchor="w", pady=(0, 10))

        results_card = self._glass_card(main, fill="#0f3034", padding=14)
        results_card._glass_outer.pack(fill=BOTH, expand=True)  # type: ignore[attr-defined]

        self.result_banner_label = ttk.Label(
            results_card,
            text="Ready — Start with Scan My PC",
            style="Banner.TLabel",
        )
        self.result_banner_label.pack(fill=X, pady=(0, 10))

        results_header = Frame(results_card, bg="#0f3034")
        results_header.pack(fill=X)
        ttk.Label(
            results_header,
            text="Results Summary",
            background="#0f3034",
            foreground=MUTED,
            font=("Segoe UI", 11, "bold"),
        ).pack(side=LEFT)
        open_logs_button = GlassButton(
            results_header,
            text="Open Reports / Logs",
            command=self.open_log_folder,
            width=154,
            height=40,
            fill="#173f44",
            active_fill="#22595e",
            foreground=TEXT,
            radius=16,
            font=("Segoe UI", 9, "bold"),
            bg="#0f3034",
        )
        open_logs_button.pack(side=RIGHT, padx=(8, 0))
        self.buttons.append(open_logs_button)
        technical_button = GlassButton(
            results_header,
            text="View Technical Details",
            command=self.view_technical_details,
            width=162,
            height=40,
            fill="#173f44",
            active_fill="#22595e",
            foreground=TEXT,
            radius=16,
            font=("Segoe UI", 9, "bold"),
            bg="#0f3034",
        )
        technical_button.pack(side=RIGHT)
        self.buttons.append(technical_button)

        self.status_label = ttk.Label(
            results_card,
            text="Ready",
            background="#0f3034",
            foreground=MUTED,
            font=("Segoe UI", 10),
        )
        self.status_label.pack(anchor="w", pady=(4, 10))

        self.output = scrolledtext.ScrolledText(
            results_card,
            bg="#0a2428",
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#246063",
            relief="flat",
            wrap="word",
            font=("Segoe UI", 12),
            height=10,
        )
        self.output.pack(fill=BOTH, expand=True)
        self.output.insert(
            END,
            "No scan has been run yet.\n\nClick Scan My PC to check for safe temporary files and app caches.\n\nTechnical details stay hidden until you click View Technical Details.",
        )
        self.output.configure(state="disabled")
        self._set_active_nav("Home")

    def _add_metric_card(
        self,
        parent: ttk.Frame,
        symbol: str,
        label: str,
        value: str,
        helper: str,
        row: int,
        column: int,
    ) -> ttk.Label:
        card = self._glass_card(parent, fill=CARD, padding=14, glow=column == 0, min_height=132)
        card._glass_outer.grid(row=row, column=column, sticky="nsew", padx=5, pady=4)  # type: ignore[attr-defined]
        ttk.Label(
            card,
            text=symbol,
            background=CARD,
            foreground=ACCENT if column == 0 else MUTED,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            card,
            text=label,
            background=CARD,
            foreground=MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(6, 0))
        value_label = ttk.Label(
            card,
            text=value,
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 16, "bold"),
            wraplength=150,
        )
        value_label.pack(anchor="w", pady=(4, 0))
        ttk.Label(
            card,
            text=helper,
            background=CARD,
            foreground=MUTED,
            font=("Segoe UI", 8),
            wraplength=155,
        ).pack(anchor="w", pady=(6, 0))
        return value_label

    def _add_sidebar_button(self, parent, label: str, command) -> None:
        def run_command() -> None:
            if label in {"Home", "Scan", "Cleanup", "Reports", "License", "Help"}:
                self._set_active_nav(label)
            command()

        button = GlassButton(
            parent,
            text=label,
            command=run_command,
            width=176,
            height=42,
            fill=SIDEBAR,
            active_fill="#1d6868",
            foreground="#e8fbf6",
            disabled_fill=SIDEBAR,
            disabled_foreground="#81aaa4",
            glow=False,
            radius=17,
            font=("Segoe UI", 10, "bold"),
            bg=SIDEBAR,
        )
        button.pack(fill=X, pady=3)
        if label in {"Home", "Scan", "Cleanup", "Reports", "License", "Help"}:
            self.sidebar_buttons[label] = button

    def _set_active_nav(self, label: str) -> None:
        for button_label, button in self.sidebar_buttons.items():
            button.configure(active=button_label == label)

    def _set_view(self, view_name: str) -> None:
        self._set_active_nav(view_name)
        subtitles = {
            "Home": "A calm, scan-first way to care for your PC.",
            "Reports": "Open reports, logs, and technical details when you need them.",
            "License": "Activate cleanup when you are ready to recover space.",
            "Help": "Safety-first cleanup with personal files protected.",
        }
        self.view_title_label.configure(text=view_name)
        self.view_subtitle_label.configure(text=subtitles.get(view_name, "Scan first, then choose cleanup."))

        if view_name == "Reports":
            self._set_result_banner("Reports — Open Latest Report or Technical Details", TEXT)
            self._clear_output()
            self._append_output("Reports are saved on your Desktop in BayouFinds_Cleanup_Logs.\n\nUse Open Reports / Logs for raw technical logs, or Open Latest Report for the customer report.\n")
        elif view_name == "License":
            self.refresh_license_state()
            self._clear_output()
            self._append_output("License options\n\nTrial mode includes Scan My PC and reports. Active licenses unlock Safe Cleanup and recovery tracking.\n\nUse Purchase License or Import License from the sidebar.\n")
        elif view_name == "Help":
            self._set_result_banner("Protected by Default", SUCCESS)
            self._clear_output()
            self._append_output("Protected by Default\n\nDocuments, Pictures, Downloads, Desktop, Videos, Music, browser passwords, and saved logins are not cleaned by default.\n\nBayouFinds does not include registry cleaning or driver cleanup.\n")

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

    def _set_dashboard_value(self, label: ttk.Label, value: str, foreground: str = TEXT) -> None:
        label.configure(text=value, foreground=foreground)

    def _set_result_banner(self, text: str, foreground: str = TEXT) -> None:
        self.result_banner_label.configure(text=text, foreground=foreground)

    def _add_primary_button(self, parent, label: str, command, side: str | None = None) -> None:
        button = GlassButton(
            parent,
            text=label,
            command=command,
            width=248,
            height=62,
            fill=PRIMARY,
            active_fill=PRIMARY_DARK,
            foreground="#082320",
            disabled_fill="#34564e",
            disabled_foreground="#b8cbc5",
            glow=True,
            radius=23,
            font=("Segoe UI", 14, "bold"),
            bg=CARD_SOFT,
        )
        pack_options = {"fill": X, "pady": 6}
        if side:
            pack_options.update({"side": side, "expand": True, "padx": 4})
        button.pack(**pack_options)
        self.buttons.append(button)

    def _add_action_button(self, parent, label: str, command, requires_license: bool = False, side: str | None = None) -> None:
        button = GlassButton(
            parent,
            text=label,
            command=command,
            width=248,
            height=48,
            fill="#1f595d",
            active_fill="#28777a",
            foreground=TEXT,
            disabled_fill="#1b3337",
            disabled_foreground="#77928e",
            glow=False,
            radius=19,
            font=("Segoe UI", 10, "bold"),
            bg=CARD_SOFT,
        )
        pack_options = {"fill": X, "pady": 5}
        if side:
            pack_options.update({"side": side, "expand": True, "padx": 4})
        button.pack(**pack_options)
        self.buttons.append(button)
        if requires_license:
            self.licensed_buttons.append(button)

    def _add_secondary_button(self, parent, label: str, command, requires_license: bool = False, side: str | None = None) -> None:
        button = GlassButton(
            parent,
            text=label,
            command=command,
            width=120,
            height=40,
            fill="#173f44",
            active_fill="#22595e",
            foreground=TEXT,
            disabled_fill="#172f33",
            disabled_foreground="#77928e",
            glow=False,
            radius=16,
            font=("Segoe UI", 9, "bold"),
            bg=CARD_SOFT,
        )
        pack_options = {"fill": X, "pady": 5}
        if side:
            pack_options.update({"side": side, "expand": True, "padx": 4})
        button.pack(**pack_options)
        self.buttons.append(button)
        if requires_license:
            self.licensed_buttons.append(button)

    def refresh_license_state(self) -> None:
        state, detail = self._read_local_license_state()
        self.license_state = state

        if state == "active":
            self._set_dashboard_value(self.license_value_label, "● ACTIVE", SUCCESS)
            self._set_result_banner("License Active — Cleanup enabled", SUCCESS)
            self._set_dashboard_value(self.recommendation_value_label, "Recommendation: Scan, then run cleanup", TEXT)
        elif state == "trial":
            self._set_dashboard_value(self.license_value_label, "● TRIAL MODE", WARNING)
            self._set_result_banner("Trial Mode — Scan and reports enabled", WARNING)
            self._set_dashboard_value(
                self.recommendation_value_label,
                "Recommendation: Purchase a license to clean",
                WARNING,
            )
        else:
            self._set_dashboard_value(self.license_value_label, "● LICENSE REQUIRED", ERROR)
            self._set_result_banner("License Required — Scan and reports enabled", WARNING)
            self._set_dashboard_value(
                self.recommendation_value_label,
                "Recommendation: Purchase or import a license",
                WARNING,
            )

        self._apply_license_button_state()
        if detail:
            self.status_label.configure(text=detail, foreground=MUTED if state != "active" else SUCCESS)

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
        prompt.title("License Required")
        prompt.geometry("500x260")
        prompt.configure(bg=BG)
        prompt.resizable(False, False)
        prompt.transient(self.root)
        prompt.grab_set()

        frame = ttk.Frame(prompt, padding=22)
        frame.pack(fill=BOTH, expand=True)
        ttk.Label(frame, text="License Required", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "License Required. Scan and reports are available in trial mode. "
                "Activate to clean and recover space."
            ),
            style="TLabel",
            wraplength=440,
        ).pack(anchor="w", pady=(10, 18))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=X)
        ttk.Button(
            buttons,
            text="Purchase License",
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
        self.status_label.configure(text="License imported", foreground=SUCCESS)
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
            "Run safe cleanup now?\n\nThis cleans safe temporary files and app caches only.\nIt will not delete your Documents, Pictures, Desktop, Videos, Music, or Downloads."
        ):
            return
        self.run_cleanup("Run Safe Cleanup", ["-NoMenu", "-Mode", "SafeCleanup"])

    def deep_cleanup(self) -> None:
        if not self._has_active_license():
            self._show_license_required_prompt()
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

    def repair_windows_files(self) -> None:
        if not self._has_active_license():
            self._show_license_required_prompt()
            return

        self.run_cleanup("Repair Windows Files", ["-NoMenu", "-Mode", "SafeCleanup", "-SkipSFC:$false"])

    def license_status(self) -> None:
        self._set_active_nav("License")
        self.run_cleanup("License Status", ["-NoMenu", "-Mode", "LicenseCheck"])

    def run_cleanup(self, action_name: str, args: list[str]) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo(WINDOW_TITLE, "Another action is already running.")
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
        self._append_output("This panel will show a cleanup breakdown when the task finishes.\n")
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

        command.extend(["-File", str(self.script_path), *args])
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
            self.status_label.configure(text="Completed successfully", foreground=SUCCESS)
            messagebox.showinfo(
                WINDOW_TITLE,
                "Task completed successfully.\n\nReview the on-screen results or click Open Latest Report before running additional actions.\n\nReports are saved on your Desktop in:\nBayouFinds_Cleanup_Logs",
            )
        else:
            self.status_label.configure(text="Completed with errors", foreground=ERROR)
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
            self.status_label.configure(text="Running...", foreground=ACCENT)
        else:
            self.status_label.configure(text="Ready", foreground=MUTED)

    def _update_dashboard_for_start(self, action_name: str) -> None:
        if action_name == "Scan My PC":
            self._set_dashboard_value(self.last_scan_value_label, "Last Scan: Running now", ACCENT)
            self._set_dashboard_value(self.recoverable_value_label, "Checking...", ACCENT)
            self._set_dashboard_value(self.recovered_run_value_label, "Not run yet", MUTED)
            self._set_dashboard_value(self.recommendation_value_label, "Recommendation: Wait for scan results", TEXT)
        elif action_name == "Run Safe Cleanup":
            self._set_dashboard_value(self.recovered_run_value_label, "Cleaning...", ACCENT)
            self._set_dashboard_value(self.recommendation_value_label, "Recommendation: Cleaning safe temporary files", TEXT)
        elif action_name == "License Status":
            self._set_dashboard_value(self.license_value_label, "Checking", ACCENT)
            self.last_license_mode = None

    def _update_dashboard_for_done(self, action_name: str | None, exit_code: int) -> None:
        now = datetime.now().strftime("%I:%M %p").lstrip("0")
        if action_name == "Scan My PC":
            if exit_code == 0:
                self._set_dashboard_value(self.last_scan_value_label, f"Last Scan: Completed at {now}", SUCCESS)
                self._set_dashboard_value(
                    self.recommendation_value_label,
                    "Recommendation: Review results, then run cleanup",
                    TEXT,
                )
            else:
                self._set_dashboard_value(self.last_scan_value_label, "Last Scan: Needs attention", ERROR)
                self._set_dashboard_value(self.recommendation_value_label, "Recommendation: Open the report before cleanup", WARNING)
        elif action_name == "Run Safe Cleanup":
            if exit_code == 0:
                self._set_dashboard_value(self.recommendation_value_label, "Recommendation: Cleanup complete", SUCCESS)
            else:
                self._set_dashboard_value(self.recommendation_value_label, "Recommendation: Review the report", WARNING)
        elif action_name == "License Status":
            if exit_code == 0 and self.last_license_mode == "licensed":
                self._set_dashboard_value(self.license_value_label, "● ACTIVE", SUCCESS)
                self.license_state = "active"
            elif exit_code == 0 and self.last_license_mode == "trial":
                self._set_dashboard_value(self.license_value_label, "● TRIAL MODE", WARNING)
                self.license_state = "trial"
            else:
                self._set_dashboard_value(self.license_value_label, "● LICENSE REQUIRED", ERROR)
                self.license_state = "required"
            self._apply_license_button_state()

    def _show_structured_breakdown(self, action_name: str | None, exit_code: int) -> None:
        report = self._load_latest_json_report()
        stats = self._load_cleanup_stats()
        self._clear_output()

        if report:
            if report.get("RunMode") == "LicenseCheck":
                self._append_output(self._format_license_breakdown(report, exit_code))
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
        recoverable = int(statistics.get("RecoverableBytes") or 0)
        recovered = int(statistics.get("RecoveredBytes") or 0)
        total_recovered = int(statistics.get("TotalRecoveredBytes") or 0)
        health_score = int(statistics.get("PCHealthScore") or 100)

        if stats:
            total_recovered = int(stats.get("TotalRecoveredBytes") or total_recovered)
            health_score = int(stats.get("PCHealthScore") or health_score)

        self._set_dashboard_value(self.recoverable_value_label, self._format_bytes(recoverable), TEXT)
        self._set_dashboard_value(self.recovered_run_value_label, self._format_bytes(recovered), SUCCESS)
        self._set_dashboard_value(self.total_recovered_value_label, self._format_bytes(total_recovered), SUCCESS)
        self._set_dashboard_value(self.health_score_value_label, f"{health_score}/100", self._health_color(health_score))

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
            f"Scan Complete — Recoverable Space Found: {self._format_gb(recoverable)}"
            if is_preview
            else f"Cleanup Complete — Space Recovered: {self._format_gb(recovered)}"
        )
        self._set_result_banner(banner, SUCCESS if exit_code == 0 else ERROR)
        lines = [
            banner,
            f"Status: {'Completed successfully' if exit_code == 0 else 'Needs attention'}",
            "",
            "Dashboard metrics",
            f"Recoverable Space: {self._format_bytes(recoverable)}",
            f"Recovered This Run: {self._format_bytes(recovered)}",
            f"Total Recovered: {self._format_bytes(total_recovered)}",
            f"PC Health Score: {health_score}/100",
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
        lines.extend([
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
    root = Tk()
    root.withdraw()
    show_splash_screen(root)
    BayouFindsCleanupGUI(root)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
