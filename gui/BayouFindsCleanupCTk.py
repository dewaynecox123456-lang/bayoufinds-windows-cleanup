"""BayouFinds Cleanup Assistant v1.5.0 CustomTkinter production GUI."""

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
from tkinter import PhotoImage, filedialog, messagebox

import customtkinter as ctk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


APP_NAME = "BayouFinds Cleanup Assistant"
APP_VERSION = "v1.5.0"
WINDOW_TITLE = f"{APP_NAME} {APP_VERSION}"
PURCHASE_URL = "https://bayoufinds.com/b/y3OJr"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 760
WINDOW_SIZE = f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"

BG = "#071b1d"
SIDEBAR = "#0a2528"
CARD = "#103338"
CARD_SOFT = "#143d42"
CARD_BORDER = "#2d6f70"
RESULT_BG = "#0a2428"
TEXT = "#f5fbf8"
MUTED = "#a8c7c2"
ACCENT = "#6fdad0"
PRIMARY = "#77e0a5"
PRIMARY_DARK = "#4bbf7c"
SUCCESS = "#7ee7a6"
WARNING = "#f1c96b"
ERROR = "#ff7c7c"


def find_asset_path(filename: str, base_dir: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if base_dir:
        candidates.append(base_dir / "assets" / "optimized" / filename)
        candidates.append(base_dir / "assets" / filename)

    repo_root = Path(__file__).resolve().parents[1]
    candidates.append(repo_root / "assets" / "optimized" / filename)
    candidates.append(repo_root / "assets" / filename)

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
                target_size = (max(1, int(source.width * scale)), max(1, int(source.height * scale)))
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
    return image.subsample(factor, factor) if factor > 1 else image


class BayouFindsCleanupCTk:
    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)

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
        self.buttons: list[ctk.CTkButton] = []
        self.licensed_buttons: list[ctk.CTkButton] = []
        self.sidebar_buttons: dict[str, ctk.CTkButton] = {}
        self.page_buttons: list[ctk.CTkButton] = []

        self._set_icon()
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

    def _set_icon(self) -> None:
        icon_path = self._asset_path("app_icon.ico")
        if icon_path:
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

    def _card(self, parent, fg_color: str = CARD, corner_radius: int = 18) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, fg_color=fg_color, corner_radius=corner_radius, border_width=1, border_color=CARD_BORDER)

    def _button(
        self,
        parent,
        text: str,
        command,
        fg_color: str = "#173f44",
        hover_color: str = "#22595e",
        text_color: str = TEXT,
        height: int = 40,
        requires_license: bool = False,
    ) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            corner_radius=14,
            height=height,
            font=("Segoe UI", 11, "bold"),
        )
        self.buttons.append(button)
        if requires_license:
            self.licensed_buttons.append(button)
        return button

    def _build_layout(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.root.configure(fg_color=BG)
        self.root.grid_columnconfigure(0, minsize=250, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self.root, width=250, corner_radius=0, fg_color=SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(sidebar, text="BayouFinds", text_color=TEXT, font=("Segoe UI", 22, "bold")).grid(
            row=0, column=0, sticky="w", padx=22, pady=(24, 0)
        )
        ctk.CTkLabel(sidebar, text="Cleanup Assistant", text_color=MUTED, font=("Segoe UI", 11)).grid(
            row=1, column=0, sticky="w", padx=22, pady=(0, 20)
        )

        nav = [
            ("Home", lambda: self.show_page("Home")),
            ("Scan", lambda: self.show_page("Scan")),
            ("Cleanup", lambda: self.show_page("Cleanup")),
            ("Reports", lambda: self.show_page("Reports")),
            ("License", lambda: self.show_page("License")),
            ("Help", lambda: self.show_page("Help")),
        ]
        for row, (label, command) in enumerate(nav, start=2):
            button = ctk.CTkButton(
                sidebar,
                text=label,
                command=command,
                fg_color=SIDEBAR,
                hover_color="#1d6868",
                text_color="#e8fbf6",
                anchor="w",
                corner_radius=14,
                height=42,
                font=("Segoe UI", 11, "bold"),
            )
            button.grid(row=row, column=0, sticky="ew", padx=16, pady=4)
            self.sidebar_buttons[label] = button

        license_panel = self._card(sidebar, "#11373b", 18)
        license_panel.grid(row=9, column=0, sticky="ew", padx=16, pady=(8, 8))
        license_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(license_panel, text="License", text_color=MUTED, font=("Segoe UI", 10, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=(12, 0)
        )
        self.license_value_label = ctk.CTkLabel(
            license_panel,
            text="LICENSE REQUIRED",
            text_color=ERROR,
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        )
        self.license_value_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 0))
        ctk.CTkLabel(
            license_panel,
            text="Trial mode: scan and reports only",
            text_color=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=190,
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(4, 12))

        self._button(sidebar, "🛒 Purchase License", self.purchase_license).grid(row=10, column=0, sticky="ew", padx=16, pady=4)
        self._button(sidebar, "Import License", self.import_license).grid(row=11, column=0, sticky="ew", padx=16, pady=(4, 8))

        reminder = self._card(sidebar, "#0f3034", 18)
        reminder.grid(row=12, column=0, sticky="ew", padx=16, pady=(0, 18))
        ctk.CTkLabel(reminder, text="Protected by Default", text_color=SUCCESS, font=("Segoe UI", 10, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=(12, 0)
        )
        ctk.CTkLabel(
            reminder,
            text="Documents, passwords, and saved logins stay protected.",
            text_color=MUTED,
            font=("Segoe UI", 9),
            wraplength=190,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 12))

        self.main = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew", padx=24, pady=22)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(4, weight=1)

        self._build_header()
        self._build_metrics()
        self._build_status_bar()
        self._build_middle_row()
        self._build_results()
        self.show_page("Home")

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self.main, fg_color=BG)
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
            fg_color="#11373b",
            corner_radius=14,
            width=92,
            height=34,
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=1, rowspan=2, sticky="ne", padx=(18, 0))

    def _build_metrics(self) -> None:
        metrics = ctk.CTkFrame(self.main, fg_color=BG)
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        for column in range(4):
            metrics.grid_columnconfigure(column, weight=1, uniform="metrics")
        self.recoverable_value_label = self._metric_card(metrics, 0, "Recoverable Space", "Not scanned yet")
        self.recovered_run_value_label = self._metric_card(metrics, 1, "Recovered This Run", "Not run yet")
        self.total_recovered_value_label = self._metric_card(metrics, 2, "Total Recovered", "No cleanup yet")
        self.health_score_value_label = self._metric_card(metrics, 3, "PC Health Score", "Not scanned yet")

    def _metric_card(self, parent, column: int, title: str, value: str) -> ctk.CTkLabel:
        card = self._card(parent, CARD, 20)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0 if column == 3 else 8))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, text_color=MUTED, font=("Segoe UI", 10, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=18, pady=(18, 4)
        )
        value_label = ctk.CTkLabel(card, text=value, text_color=TEXT, font=("Segoe UI", 17, "bold"), anchor="w")
        value_label.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
        return value_label

    def _build_status_bar(self) -> None:
        status = self._card(self.main, "#0f3034", 20)
        status.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        for column in range(3):
            status.grid_columnconfigure(column, weight=1, uniform="status")
        self.last_scan_value_label = self._status_item(status, 0, "Last Scan", "Not scanned yet")
        self.recommendation_value_label = self._status_item(status, 1, "Recommendation", "Run a scan to see results")
        self.status_license_value_label = self._status_item(status, 2, "License Status", "License Required", ERROR)

    def _status_item(self, parent, column: int, title: str, value: str, color: str = TEXT) -> ctk.CTkLabel:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=column, sticky="ew", padx=18, pady=14)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, text_color=MUTED, font=("Segoe UI", 10, "bold"), anchor="w").grid(row=0, column=0, sticky="ew")
        value_label = ctk.CTkLabel(frame, text=value, text_color=color, font=("Segoe UI", 12, "bold"), anchor="w")
        value_label.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        return value_label

    def _build_middle_row(self) -> None:
        middle = ctk.CTkFrame(self.main, fg_color=BG)
        middle.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        middle.grid_columnconfigure(0, weight=1, uniform="middle")
        middle.grid_columnconfigure(1, weight=1, uniform="middle")

        self.action_card = self._card(middle, CARD_SOFT, 22)
        self.action_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.action_card.grid_columnconfigure(0, weight=1)
        self.action_title_label = ctk.CTkLabel(self.action_card, text="Start Here", text_color=TEXT, font=("Segoe UI", 20, "bold"), anchor="w")
        self.action_title_label.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 4))
        self.action_body_label = ctk.CTkLabel(
            self.action_card,
            text="Run a safe scan to estimate recoverable space.\nNo files are deleted during a scan.",
            text_color=MUTED,
            font=("Segoe UI", 12),
            anchor="w",
            justify="left",
        )
        self.action_body_label.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 8))
        self.action_status_label = ctk.CTkLabel(
            self.action_card,
            text="Status: Ready",
            text_color=SUCCESS,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        self.action_status_label.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 12))
        self.action_buttons_frame = ctk.CTkFrame(self.action_card, fg_color="transparent")

        protected = self._card(middle, CARD, 22)
        protected.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        protected.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(protected, text="Protected by Default", text_color=SUCCESS, font=("Segoe UI", 16, "bold"), anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=22, pady=(22, 10)
        )
        protected_items = ["Documents", "Pictures", "Downloads", "Desktop", "Videos", "Music", "Browser Passwords", "Saved Logins"]
        for index, item in enumerate(protected_items):
            ctk.CTkLabel(protected, text=f"✓ {item}", text_color=TEXT, font=("Segoe UI", 11, "bold"), anchor="w").grid(
                row=1 + (index // 2), column=index % 2, sticky="ew", padx=22, pady=3
            )

    def _build_results(self) -> None:
        results = self._card(self.main, "#0f3034", 22)
        results.grid(row=4, column=0, sticky="nsew")
        results.grid_columnconfigure(0, weight=1)
        results.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(results, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 4))
        header.grid_columnconfigure(0, weight=1)
        self.result_banner_label = ctk.CTkLabel(header, text="Scan Results", text_color=TEXT, font=("Segoe UI", 18, "bold"), anchor="w")
        self.result_banner_label.grid(row=0, column=0, sticky="ew")
        self._button(header, "View Technical Details", self.view_technical_details, height=38).grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.status_label = ctk.CTkLabel(results, text="Ready", text_color=MUTED, font=("Segoe UI", 11, "bold"), anchor="w")
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
            "No scans have been run yet.\n\n"
            "Click Scan in the left menu to check for safe temporary files and app caches.\n\n"
            "Results will appear here after your scan completes.",
        )
        self.output.configure(state="disabled")

    def show_page(self, page: str) -> None:
        self._set_active_nav(page)
        self._clear_page_buttons()
        titles = {
            "Home": "Welcome to BayouFinds Cleanup Assistant",
            "Scan": "Scan",
            "Cleanup": "Cleanup",
            "Reports": "Reports",
            "License": "License",
            "Help": "Help",
        }
        subtitles = {
            "Home": "Scan your PC to find and safely remove unnecessary files.",
            "Scan": "Run a safe scan to estimate recoverable space. Scans do not delete files.",
            "Cleanup": "Run Safe Cleanup after activation.",
            "Reports": "Open reports, logs, and technical details.",
            "License": "Purchase or import a license to unlock cleanup.",
            "Help": "Safety-first cleanup with personal files protected.",
        }
        self.view_title_label.configure(text=titles.get(page, page))
        self.view_subtitle_label.configure(text=subtitles.get(page, ""))

        if page == "Home":
            self.action_title_label.configure(text="Start Here")
            self.action_body_label.configure(text="Run a safe scan to estimate recoverable space.\nNo files are deleted during a scan.")
            self.action_status_label.configure(text="Status: Ready", text_color=SUCCESS)
            self._reset_home_results()
        elif page == "Scan":
            self.action_title_label.configure(text="Scan My PC")
            self.action_body_label.configure(text="Scan checks safe temporary files and app caches. It does not delete files.")
            self.action_status_label.configure(text="Status: Ready to scan", text_color=ACCENT)
            self._add_page_button("Scan My PC", self.scan_my_pc, PRIMARY, PRIMARY_DARK, "#082320")
        elif page == "Cleanup":
            self.action_title_label.configure(text="Run Safe Cleanup")
            self.action_body_label.configure(text="Safe Cleanup removes approved temporary files and app caches only.")
            self.action_status_label.configure(
                text="Status: Cleanup enabled" if self.license_state == "active" else "Status: Activate license to run cleanup",
                text_color=SUCCESS if self.license_state == "active" else WARNING,
            )
            self._add_page_button("Run Safe Cleanup", self.quick_cleanup, "#1f595d", "#28777a", TEXT, requires_license=True)
        elif page == "Reports":
            self.action_title_label.configure(text="Reports")
            self.action_body_label.configure(text="Reports are saved on your Desktop in BayouFinds_Cleanup_Logs.")
            self.action_status_label.configure(text="Status: Reports available after scan", text_color=ACCENT)
            self._add_page_button("Open Latest Report", self.open_latest_report, "#173f44", "#22595e", TEXT)
            self._add_page_button("Open Reports / Logs", self.open_log_folder, "#173f44", "#22595e", TEXT)
            self._add_page_button("View Technical Details", self.view_technical_details, "#173f44", "#22595e", TEXT)
        elif page == "License":
            self.refresh_license_state()
            self.action_title_label.configure(text="License")
            self.action_body_label.configure(text="Import your license file or purchase a license to unlock cleanup.")
            self.action_status_label.configure(text=f"Status: {self._license_display_text()}", text_color=self._license_color())
            self._add_page_button("Import License", self.import_license, "#173f44", "#22595e", TEXT)
            self._add_page_button("🛒 Purchase License", self.purchase_license, "#173f44", "#22595e", TEXT)
        elif page == "Help":
            self.action_title_label.configure(text="Help")
            self.action_body_label.configure(text="BayouFinds protects personal folders by default and does not include registry or driver cleanup.")
            self.action_status_label.configure(text="Status: Safety guardrails active", text_color=SUCCESS)
            self._set_result_banner("Protected by Default", SUCCESS)
            self._clear_output()
            self._append_output(
                "Protected by Default\n\n"
                "Documents, Pictures, Downloads, Desktop, Videos, Music, browser passwords, and saved logins are not cleaned by default.\n\n"
                "BayouFinds does not include registry cleaning or driver cleanup."
            )
        self._apply_license_button_state()

    def _reset_home_results(self) -> None:
        self._set_result_banner("Scan Results", TEXT)
        self._clear_output()
        self._append_output(
            "No scans have been run yet.\n\n"
            "Click Scan in the left menu to check for safe temporary files and app caches.\n\n"
            "Results will appear here after your scan completes."
        )

    def _clear_page_buttons(self) -> None:
        for button in self.page_buttons:
            if button in self.buttons:
                self.buttons.remove(button)
            if button in self.licensed_buttons:
                self.licensed_buttons.remove(button)
        for child in self.action_buttons_frame.winfo_children():
            child.destroy()
        self.page_buttons = []
        self.action_buttons_frame.grid_forget()

    def _add_page_button(self, text: str, command, fg_color: str, hover_color: str, text_color: str, requires_license: bool = False) -> None:
        self.action_buttons_frame.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 22))
        self.action_buttons_frame.grid_columnconfigure(0, weight=1)
        button = self._button(self.action_buttons_frame, text, command, fg_color, hover_color, text_color, 42, requires_license)
        button.grid(row=len(self.page_buttons), column=0, sticky="ew", pady=4)
        self.page_buttons.append(button)
