"""BayouFinds Windows Cleanup v1.3.0 Tkinter GUI."""

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
from tkinter import PhotoImage, Tk, Toplevel, filedialog, messagebox
from tkinter import BOTH, END, LEFT, RIGHT, X, Y
from tkinter import scrolledtext, ttk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


APP_NAME = "BayouFinds Cleanup Assistant"
APP_VERSION = "v1.3.0"
WINDOW_TITLE = f"{APP_NAME} {APP_VERSION} Beta"
WINDOW_SIZE = "940x620"
WINDOW_WIDTH = 940
WINDOW_HEIGHT = 620
CONTENT_PADDING = 18
HEADER_IMAGE_MAX_WIDTH = WINDOW_WIDTH - (CONTENT_PADDING * 2)
HEADER_IMAGE_MAX_HEIGHT = 96
MASCOT_IMAGE_MAX_WIDTH = 170
MASCOT_IMAGE_MAX_HEIGHT = 170
SPLASH_WIDTH = 620
SPLASH_HEIGHT = 360
SPLASH_IMAGE_MAX_WIDTH = 584
SPLASH_IMAGE_MAX_HEIGHT = 292

BG = "#10242a"
PANEL = "#183039"
PANEL_ALT = "#213d46"
PANEL_SOFT = "#1f3a43"
TEXT = "#f5f8f7"
MUTED = "#b8c9c7"
ACCENT = "#39a9c7"
ACCENT_DARK = "#2388a3"
PRIMARY = "#69c7a5"
PRIMARY_DARK = "#4ba985"
SUCCESS = "#7bd88f"
WARNING = "#f4c76b"
ERROR = "#ff7a7a"


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
        self.images: list[PhotoImage] = []

        self._configure_styles()
        self._set_icon()
        self._build_menu()
        self._build_layout()
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
        style.configure("SoftPanel.TFrame", background=PANEL_SOFT)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 22, "bold"))
        style.configure("Subheader.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 11))
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
            foreground="#09231e",
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 12, "bold"),
            padding=(16, 14),
        )
        style.map(
            "Primary.TButton",
            background=[("active", PRIMARY_DARK), ("disabled", "#47665d")],
            foreground=[("disabled", "#c4d1cd")],
        )
        style.configure(
            "Action.TButton",
            background=ACCENT,
            foreground="white",
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 10, "bold"),
            padding=(14, 10),
        )
        style.map(
            "Action.TButton",
            background=[("active", ACCENT_DARK), ("disabled", "#405465")],
            foreground=[("disabled", "#b9c4ce")],
        )
        style.configure(
            "Secondary.TButton",
            background=PANEL_ALT,
            foreground=TEXT,
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 10),
            padding=(14, 10),
        )
        style.map("Secondary.TButton", background=[("active", "#284154")])

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
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill=BOTH, expand=True)

        header = ttk.Frame(outer)
        header.pack(fill=X)

        header_image = self._load_image_fit(
            "header_banner.png",
            HEADER_IMAGE_MAX_WIDTH,
            HEADER_IMAGE_MAX_HEIGHT,
            allow_upscale=True,
        )
        if header_image:
            ttk.Label(header, image=header_image, background=BG).pack(anchor="center", fill=X)
        else:
            ttk.Label(header, text="BayouFinds", style="Header.TLabel").pack(anchor="w")
            ttk.Label(
                header,
                text="Scan first, review results, then run safe cleanup",
                style="Subheader.TLabel",
            ).pack(anchor="w", pady=(2, 0))

        ttk.Label(header, text=WINDOW_TITLE, style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

        body = ttk.Frame(outer)
        body.pack(fill=BOTH, expand=True, pady=(14, 0))

        controls = ttk.Frame(body, style="Panel.TFrame", padding=14)
        controls.pack(side=LEFT, fill=Y)
        controls.configure(width=285)
        controls.pack_propagate(False)

        ttk.Label(
            controls,
            text="Home PC care",
            background=PANEL,
            foreground=TEXT,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            controls,
            text="Scan first. Nothing is deleted until you choose cleanup.",
            background=PANEL,
            foreground=MUTED,
            font=("Segoe UI", 9),
            wraplength=250,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))

        self.buttons: list[ttk.Button] = []
        self._add_action_button(controls, "Import License", self.import_license)
        self._add_primary_button(controls, "Scan My PC", self.scan_my_pc)
        self._add_action_button(controls, "Run Safe Cleanup", self.quick_cleanup)
        self._add_secondary_button(controls, "Open Latest Report", self.open_latest_report)
        self._add_secondary_button(controls, "Open Reports / Logs", self.open_log_folder)

        ttk.Separator(controls).pack(fill=X, pady=10)
        ttk.Label(
            controls,
            text="More tools",
            background=PANEL,
            foreground=MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        self._add_secondary_button(controls, "License Status", self.license_status)
        self._add_secondary_button(controls, "Deep Windows Check", self.deep_cleanup)
        self._add_secondary_button(controls, "Repair Windows Files", self.repair_windows_files)
        self._add_secondary_button(controls, "About", self.show_about)
        self._add_secondary_button(controls, "Exit", self.root.destroy)

        output_panel = ttk.Frame(body, style="Panel.TFrame", padding=14)
        output_panel.pack(side=RIGHT, fill=BOTH, expand=True, padx=(16, 0))

        dashboard = ttk.Frame(output_panel, style="SoftPanel.TFrame", padding=12)
        dashboard.pack(fill=X, pady=(0, 12))

        self.license_value_label = self._add_dashboard_row(dashboard, "License", "Not checked")
        self.last_scan_value_label = self._add_dashboard_row(dashboard, "Last Scan", "Not run yet")
        self.recommendation_value_label = self._add_dashboard_row(
            dashboard,
            "Recommendation",
            "Start with Scan My PC",
        )
        self.safety_value_label = self._add_dashboard_row(
            dashboard,
            "Safety",
            "Personal files protected",
        )

        ttk.Label(
            output_panel,
            text="Scan Results",
            background=PANEL,
            foreground=TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

        self.status_label = ttk.Label(
            output_panel,
            text="Ready",
            background=PANEL,
            foreground=MUTED,
            font=("Segoe UI", 10),
        )
        self.status_label.pack(anchor="w", pady=(4, 10))

        self.output = scrolledtext.ScrolledText(
            output_panel,
            bg="#071019",
            fg="#e7edf4",
            insertbackground=TEXT,
            selectbackground=ACCENT_DARK,
            relief="flat",
            wrap="word",
            font=("Segoe UI", 10),
            height=18,
        )
        self.output.pack(fill=BOTH, expand=True)
        self.output.insert(
            END,
            "Welcome to BayouFinds Cleanup Assistant.\n\nClick Scan My PC to check safe cleanup areas and create a report. The scan does not delete files.\n\nAfter the scan, review the results here or open the latest report. Use Run Safe Cleanup only when you are ready.\n\nSafety promise:\nBayouFinds protects your Documents, Pictures, Desktop, Videos, Music, and Downloads by default.\nRegistry cleaning and driver cleanup are not included.\n\nReports and logs are saved to your Desktop in BayouFinds_Cleanup_Logs.\n\n",
        )
        self.output.configure(state="disabled")

    def _add_dashboard_row(self, parent: ttk.Frame, label: str, value: str) -> ttk.Label:
        row = ttk.Frame(parent, style="SoftPanel.TFrame")
        row.pack(fill=X, pady=2)
        ttk.Label(
            row,
            text=f"{label}:",
            style="DashboardTitle.TLabel",
            width=15,
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

    def _add_primary_button(self, parent: ttk.Frame, label: str, command) -> None:
        button = ttk.Button(parent, text=label, style="Primary.TButton", command=command)
        button.pack(fill=X, pady=6)
        self.buttons.append(button)

    def _add_action_button(self, parent: ttk.Frame, label: str, command) -> None:
        button = ttk.Button(parent, text=label, style="Action.TButton", command=command)
        button.pack(fill=X, pady=5)
        self.buttons.append(button)

    def _add_secondary_button(self, parent: ttk.Frame, label: str, command) -> None:
        button = ttk.Button(parent, text=label, style="Secondary.TButton", command=command)
        button.pack(fill=X, pady=5)
        self.buttons.append(button)

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
        self._set_dashboard_value(self.license_value_label, "Valid", SUCCESS)
        self._set_dashboard_value(self.recommendation_value_label, "Click Scan My PC next", TEXT)
        messagebox.showinfo(
            WINDOW_TITLE,
            f"License imported successfully.\n\nCustomer: {customer}\nExpires: {expires}\n\nYou can now click License Status to verify activation.",
        )

    def quick_cleanup(self) -> None:
        if not messagebox.askyesno(
            "Run Safe Cleanup",
            "Run safe cleanup now?\n\nThis cleans safe temporary/cache locations only.\nIt will not delete your Documents, Pictures, Desktop, Videos, Music, or Downloads."
        ):
            return
        self.run_cleanup("Run Safe Cleanup", ["-NoMenu", "-Mode", "SafeCleanup"])

    def deep_cleanup(self) -> None:
        if not messagebox.askyesno(
            "Deep Windows Check",
            "Deep Windows Check may take longer because it runs additional Windows file checks.\n\nIt still uses the safe cleanup engine. Continue?"
        ):
            return
        self.run_cleanup("Deep Windows Check", ["-NoMenu", "-Mode", "SafeCleanup", "-SkipSFC:$false"])

    def scan_my_pc(self) -> None:
        self.run_cleanup("Scan My PC", ["-NoMenu", "-Mode", "Preview"])

    def repair_windows_files(self) -> None:
        self.run_cleanup("Repair Windows Files", ["-NoMenu", "-Mode", "SafeCleanup", "-SkipSFC:$false"])

    def license_status(self) -> None:
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
        self._update_dashboard_for_start(action_name)
        self._clear_output()
        self._append_output(f"Starting {action_name}...\n")
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
                    self._append_output(line)
                    self._capture_license_mode(line)
                elif event == "done":
                    self._handle_done(int(payload or 0))
        except queue.Empty:
            pass

        self.root.after(100, self._poll_output_queue)

    def _handle_done(self, exit_code: int) -> None:
        self._append_output(f"\nFinished with exit code {exit_code}.\n")
        self._append_output(f"Reports and logs are saved here:\n{self.log_folder}\n")
        action_name = self.current_action_name
        self.current_action_name = None
        self._set_running(False)
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

        if running:
            self.status_label.configure(text="Running...", foreground=ACCENT)
        else:
            self.status_label.configure(text="Ready", foreground=MUTED)

    def _update_dashboard_for_start(self, action_name: str) -> None:
        if action_name == "Scan My PC":
            self._set_dashboard_value(self.last_scan_value_label, "Running now", ACCENT)
            self._set_dashboard_value(self.recommendation_value_label, "Wait for scan results", TEXT)
        elif action_name == "Run Safe Cleanup":
            self._set_dashboard_value(self.recommendation_value_label, "Cleaning safe temporary files", TEXT)
        elif action_name == "License Status":
            self._set_dashboard_value(self.license_value_label, "Checking", ACCENT)
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
        elif action_name == "Run Safe Cleanup":
            if exit_code == 0:
                self._set_dashboard_value(self.recommendation_value_label, "Cleanup complete", SUCCESS)
            else:
                self._set_dashboard_value(self.recommendation_value_label, "Review the report", WARNING)
        elif action_name == "License Status":
            if exit_code == 0 and self.last_license_mode in {"licensed", "trial"}:
                self._set_dashboard_value(self.license_value_label, "Valid", SUCCESS)
            else:
                self._set_dashboard_value(self.license_value_label, "Needs attention", ERROR)

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

    def _find_latest_report(self) -> Path | None:
        if not self.log_folder.exists():
            return None

        reports = sorted(
            self.log_folder.glob("cleanup_report_*.html"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
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
