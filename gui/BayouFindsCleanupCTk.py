"""BayouFinds Cleanup Assistant v1.5.0 CustomTkinter production GUI."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
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

    def _set_active_nav(self, label: str) -> None:
        for button_label, button in self.sidebar_buttons.items():
            button.configure(fg_color="#1d6868" if button_label == label else SIDEBAR)

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

    def _license_display_text(self) -> str:
        if self.license_state == "active":
            return "Active"
        if self.license_state == "trial":
            return "Trial Mode"
        return "License Required"

    def _license_color(self) -> str:
        if self.license_state == "active":
            return SUCCESS
        if self.license_state == "trial":
            return WARNING
        return ERROR

    def _sync_license_labels(self) -> None:
        if self.license_state == "active":
            text = "● ACTIVE"
            color = SUCCESS
        elif self.license_state == "trial":
            text = "● TRIAL MODE"
            color = WARNING
        else:
            text = "● LICENSE REQUIRED"
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
            self._set_dashboard_value(self.recommendation_value_label, "Purchase a license to clean", WARNING)
        else:
            self._sync_license_labels()
            self._set_dashboard_value(self.recommendation_value_label, "Purchase or import a license", WARNING)

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
        prompt = ctk.CTkToplevel(self.root)
        prompt.title("License Required")
        prompt.geometry("520x260")
        prompt.resizable(False, False)
        prompt.transient(self.root)
        prompt.grab_set()
        prompt.configure(fg_color=BG)
        prompt.grid_columnconfigure(0, weight=1)

        frame = self._card(prompt, CARD, 20)
        frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text="License Required", text_color=ERROR, font=("Segoe UI", 20, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=20, pady=(20, 8)
        )
        ctk.CTkLabel(
            frame,
            text="License Required. Scan and reports are available in trial mode. Activate to clean and recover space.",
            text_color=TEXT,
            font=("Segoe UI", 12),
            justify="left",
            wraplength=440,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 18))

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        buttons.grid_columnconfigure((0, 1, 2), weight=1, uniform="license_prompt")
        self._button(buttons, "Purchase License", lambda: (prompt.destroy(), self.purchase_license()), PRIMARY, PRIMARY_DARK, "#082320").grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        self._button(buttons, "Import License", lambda: (prompt.destroy(), self.import_license())).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        self._button(buttons, "Not Now", prompt.destroy, "#173f44", "#22595e", TEXT).grid(row=0, column=2, sticky="ew", padx=(6, 0))

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
            messagebox.showerror(WINDOW_TITLE, f"Could not read this license file.\n\n{exc}")
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
            messagebox.showerror(WINDOW_TITLE, f"Could not install the license file.\n\n{exc}")
            return

        self._append_output(
            f"License imported successfully.\nInstalled to: {destination}\nCustomer: {customer}\nExpires: {expires}\n\n"
        )
        self._configure_text(self.status_label, "License imported", SUCCESS)
        self.refresh_license_state()
        messagebox.showinfo(
            WINDOW_TITLE,
            f"License imported successfully.\n\nCustomer: {customer}\nExpires: {expires}\n\nYou can now run cleanup if the license is active.",
        )

    def quick_cleanup(self) -> None:
        self._set_active_nav("Cleanup")
        if not self._has_active_license():
            self._show_license_required_prompt()
            return

        if not messagebox.askyesno(
            "Run Safe Cleanup",
            "Run safe cleanup now?\n\nThis cleans safe temporary files and app caches only.\nIt will not delete your Documents, Pictures, Desktop, Videos, Music, or Downloads.",
        ):
            return
        self.run_cleanup("Run Safe Cleanup", ["-NoMenu", "-Mode", "SafeCleanup"])

    def scan_my_pc(self) -> None:
        self._set_active_nav("Scan")
        self.run_cleanup("Scan My PC", ["-NoMenu", "-Mode", "Preview"])

    def run_cleanup(self, action_name: str, args: list[str]) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo(WINDOW_TITLE, "Another action is already running.")
            return

        if not self.script_path.exists():
            messagebox.showerror(WINDOW_TITLE, f"Cleanup script was not found:\n{self.script_path}")
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

        self._configure_text(self.status_label, "Running..." if running else "Ready", ACCENT if running else MUTED)

    def _update_dashboard_for_start(self, action_name: str) -> None:
        if action_name == "Scan My PC":
            self._set_dashboard_value(self.last_scan_value_label, "Running now", ACCENT)
            self._set_dashboard_value(self.recoverable_value_label, "Checking...", ACCENT)
            self._set_dashboard_value(self.recovered_run_value_label, "Not run yet", MUTED)
            self._set_dashboard_value(self.recommendation_value_label, "Wait for scan results", TEXT)
        elif action_name == "Run Safe Cleanup":
            self._set_dashboard_value(self.recovered_run_value_label, "Cleaning...", ACCENT)
            self._set_dashboard_value(self.recommendation_value_label, "Cleaning safe temporary files", TEXT)

    def _update_dashboard_for_done(self, action_name: str | None, exit_code: int) -> None:
        now = datetime.now().strftime("%I:%M %p").lstrip("0")
        if action_name == "Scan My PC":
            if exit_code == 0:
                self._set_dashboard_value(self.last_scan_value_label, f"Completed at {now}", SUCCESS)
                self._set_dashboard_value(self.recommendation_value_label, "Review results, then run cleanup", TEXT)
            else:
                self._set_dashboard_value(self.last_scan_value_label, "Needs attention", ERROR)
                self._set_dashboard_value(self.recommendation_value_label, "Open the report before cleanup", WARNING)
        elif action_name == "Run Safe Cleanup":
            if exit_code == 0:
                self._set_dashboard_value(self.recommendation_value_label, "Cleanup complete", SUCCESS)
            else:
                self._set_dashboard_value(self.recommendation_value_label, "Review the report", WARNING)

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
        lines.extend(
            [
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
            ]
        )
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
        return "\n".join(
            [
                f"License Status: {status}",
                "",
                f"Mode: {mode}",
                f"Message: {message}",
                f"Exit code: {exit_code}",
                "",
                "Cleanup dashboard metrics were not changed by this license check.",
                "",
            ]
        )

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
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
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
        about = ctk.CTkToplevel(self.root)
        about.title(f"About {APP_NAME}")
        about.geometry("460x320")
        about.resizable(False, False)
        about.transient(self.root)
        about.grab_set()
        about.configure(fg_color=BG)
        about.grid_columnconfigure(0, weight=1)

        frame = self._card(about, CARD, 20)
        frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=APP_NAME, text_color=TEXT, font=("Segoe UI", 20, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=20, pady=(20, 4)
        )
        ctk.CTkLabel(frame, text=APP_VERSION, text_color=ACCENT, font=("Segoe UI", 13, "bold"), anchor="w").grid(
            row=1, column=0, sticky="ew", padx=20, pady=(0, 12)
        )
        ctk.CTkLabel(frame, text="Built by BayouFinds", text_color=TEXT, font=("Segoe UI", 12), anchor="w").grid(
            row=2, column=0, sticky="ew", padx=20, pady=(0, 4)
        )
        ctk.CTkLabel(
            frame,
            text="A scan-first Windows cleanup and reporting utility for home users.",
            text_color=MUTED,
            font=("Segoe UI", 12),
            wraplength=380,
            justify="left",
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18))
        self._button(frame, "Close", about.destroy).grid(row=4, column=0, sticky="e", padx=20, pady=(0, 20))

def main() -> None:
    print("Starting BayouFinds Cleanup Assistant CTk GUI...", flush=True)
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    root = ctk.CTk()
    root.title(WINDOW_TITLE)
    root.geometry(WINDOW_SIZE)
    root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)

    BayouFindsCleanupCTk(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
