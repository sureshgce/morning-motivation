"""
Morning Momentum Bot  v2.0.0
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Monitors a public GitHub repo for new motivational images and displays
them as picture-in-picture popups on Windows.

Runs as a standalone .exe — no Python installation required.

Usage (exe):
    morning_bot.exe                # normal start (tray icon)
    morning_bot.exe --check-now    # single check then exit
    morning_bot.exe --show-last    # show the last cached image

Usage (dev):
    python morning_bot.py          # same as above

Author : Morning Momentum Project
License: MIT
"""

# ── stdlib ────────────────────────────────────────────────────────────
import json
import logging
import logging.handlers
import math
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# ── 3rd-party ─────────────────────────────────────────────────────────
import requests
from PIL import Image, ImageDraw, ImageTk
import tkinter as tk
import pystray
from pystray import MenuItem

# ── Constants ─────────────────────────────────────────────────────────
APP_NAME = "Morning Momentum"
APP_VERSION = "2.0.0"

# Handle PyInstaller frozen exe vs normal Python script
if getattr(sys, "frozen", False):
    # Running as compiled exe — BASE_DIR is where the .exe lives
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # Running as .py script
    BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "config.json"
STATE_FILE = BASE_DIR / ".bot_state.json"
PID_FILE = BASE_DIR / ".bot.pid"
LOG_FILE = BASE_DIR / "morning_bot.log"

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tif", ".tiff", ".svg", ".ico", ".heic", ".heif",
    ".avif", ".jfif",
}

GITHUB_API = "https://api.github.com"
MAX_RETRIES = 3
RETRY_BACKOFF = 5  # seconds

# ── Logging ───────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    """Configure dual logging: rotating file + console."""
    logger = logging.getLogger("morning_bot")
    if logger.handlers:
        return logger  # already configured (avoid duplicate handlers)
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (5 MB × 3 backups)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler (only if not frozen — exe has no console)
    if not getattr(sys, "frozen", False):
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


log = setup_logging()

# ── Configuration ─────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "github": {
        "owner": "sureshgce",
        "repo": "morning-motivation",
        "branch": "main",
        "image_path": "images",
        "token": "",
    },
    "polling": {
        "interval_seconds": 180,
        "active_hours": {"start": "06:00", "end": "22:00"},
    },
    "popup": {
        "max_width": 600,
        "max_height": 500,
        "display_seconds": 30,
        "opacity": 0.95,
        "position": "bottom-right",
    },
    "storage": {
        "image_cache_dir": "images",
        "max_cache_days": 30,
    },
}


def load_config() -> dict:
    """Load config.json, creating it with defaults if missing."""
    if not CONFIG_FILE.exists():
        log.warning("config.json not found — creating default at %s", CONFIG_FILE)
        CONFIG_FILE.write_text(
            json.dumps(DEFAULT_CONFIG, indent=4), encoding="utf-8"
        )

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Validate required fields
    gh = config.get("github", {})
    if not gh.get("owner") or gh["owner"] == "CHANGE_ME":
        log.error("Please set 'github.owner' in config.json")
        _show_error_popup(
            "Configuration Error",
            "Please edit config.json and set 'github.owner'.\n\n"
            f"File: {CONFIG_FILE}",
        )
        sys.exit(1)
    if not gh.get("repo"):
        log.error("Please set 'github.repo' in config.json")
        sys.exit(1)

    # Merge defaults for any missing keys
    for section, defaults in DEFAULT_CONFIG.items():
        config.setdefault(section, {})
        if isinstance(defaults, dict):
            for k, v in defaults.items():
                config[section].setdefault(k, v)

    return config


def _show_error_popup(title: str, message: str):
    """Show a simple error dialog (works even without full bot init)."""
    try:
        root = tk.Tk()
        root.withdraw()
        import tkinter.messagebox as mb
        mb.showerror(title, message)
        root.destroy()
    except Exception:
        pass

# ── State Management ──────────────────────────────────────────────────

class BotState:
    """Persists the set of already-seen image SHA hashes to disk."""

    def __init__(self):
        self.seen: Dict[str, str] = {}  # sha -> filename
        self.last_image: Optional[str] = None
        self._load()

    def _load(self):
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                self.seen = data.get("seen", {})
                self.last_image = data.get("last_image")
            except (json.JSONDecodeError, KeyError):
                log.warning("Corrupt state file — resetting.")
                self.seen = {}
                self.last_image = None

    def _save(self):
        STATE_FILE.write_text(
            json.dumps({"seen": self.seen, "last_image": self.last_image}, indent=2),
            encoding="utf-8",
        )

    def is_new(self, file_info: dict) -> bool:
        return file_info["sha"] not in self.seen

    def get_new_images(self, file_list: List[dict]) -> List[dict]:
        return [f for f in file_list if self.is_new(f)]

    def mark_seen(self, file_info: dict, local_path: str):
        self.seen[file_info["sha"]] = file_info["name"]
        self.last_image = local_path
        self._save()

# ── GitHub Monitor ────────────────────────────────────────────────────

class GitHubMonitor:
    """Polls the GitHub Contents API for new images."""

    def __init__(self, config: dict):
        gh = config["github"]
        self.owner = gh["owner"]
        self.repo = gh["repo"]
        self.branch = gh.get("branch", "main")
        self.image_path = gh.get("image_path", "images")
        self.token = gh.get("token", "")
        self.etag: Optional[str] = None

        self.session = requests.Session()
        self.session.headers["Accept"] = "application/vnd.github.v3+json"
        self.session.headers["User-Agent"] = f"{APP_NAME}/{APP_VERSION}"
        if self.token:
            self.session.headers["Authorization"] = f"token {self.token}"

    def get_image_list(self) -> Optional[List[dict]]:
        """
        Fetch list of image files from the repo folder.
        Returns None on 304 (not modified) or error.
        Returns [] if folder is empty.
        Returns list of file dicts on success.
        """
        # Build URL — if image_path is empty, query repo root
        path_segment = self.image_path.strip("/") if self.image_path else ""
        if path_segment:
            url = (
                f"{GITHUB_API}/repos/{self.owner}/{self.repo}"
                f"/contents/{path_segment}"
            )
        else:
            url = f"{GITHUB_API}/repos/{self.owner}/{self.repo}/contents"

        params = {"ref": self.branch}
        headers = {}
        if self.etag:
            headers["If-None-Match"] = self.etag

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(
                    url, params=params, headers=headers, timeout=30
                )

                if resp.status_code == 304:
                    log.debug("GitHub: not modified (ETag cache hit)")
                    return None

                if resp.status_code == 403:
                    remaining = resp.headers.get("X-RateLimit-Remaining", "?")
                    reset = resp.headers.get("X-RateLimit-Reset", "")
                    reset_str = ""
                    if reset:
                        reset_str = datetime.fromtimestamp(int(reset)).strftime(
                            "%H:%M:%S"
                        )
                    log.warning(
                        "GitHub rate-limited. Remaining: %s, resets at %s",
                        remaining,
                        reset_str,
                    )
                    return None

                if resp.status_code == 404:
                    log.warning(
                        "Path not found: %s/%s/%s — trying repo root as fallback",
                        self.owner,
                        self.repo,
                        self.image_path,
                    )
                    # Fallback: try repo root (images may not be in a subfolder)
                    if path_segment:
                        return self._get_root_images()
                    return None

                resp.raise_for_status()
                self.etag = resp.headers.get("ETag")

                files = resp.json()
                if not isinstance(files, list):
                    log.error("Unexpected API response (not a list)")
                    return None

                images = [
                    f
                    for f in files
                    if f.get("type") == "file"
                    and Path(f["name"]).suffix.lower() in IMAGE_EXTENSIONS
                ]
                log.debug("GitHub: found %d images in repo", len(images))
                return images

            except requests.ConnectionError:
                log.warning(
                    "Network error (attempt %d/%d)", attempt, MAX_RETRIES
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF * attempt)
            except requests.RequestException as exc:
                log.error("GitHub API error: %s", exc)
                return None

        return None

    def _get_root_images(self) -> Optional[List[dict]]:
        """Fallback: fetch images from repo root (no subfolder)."""
        url = f"{GITHUB_API}/repos/{self.owner}/{self.repo}/contents"
        try:
            resp = self.session.get(
                url, params={"ref": self.branch}, timeout=30
            )
            resp.raise_for_status()
            files = resp.json()
            if not isinstance(files, list):
                return None
            images = [
                f
                for f in files
                if f.get("type") == "file"
                and Path(f["name"]).suffix.lower() in IMAGE_EXTENSIONS
            ]
            if images:
                log.info(
                    "Fallback: found %d images at repo root", len(images)
                )
            return images
        except requests.RequestException as exc:
            log.error("Root fallback failed: %s", exc)
            return None

    def download_image(self, file_info: dict, save_dir: Path) -> Optional[Path]:
        """Download a single image file. Returns local path or None."""
        save_path = save_dir / file_info["name"]
        if save_path.exists():
            log.debug("Image already cached: %s", save_path.name)
            return save_path

        download_url = file_info.get("download_url")
        if not download_url:
            log.error("No download URL for %s", file_info["name"])
            return None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(download_url, timeout=120)
                resp.raise_for_status()
                save_path.write_bytes(resp.content)
                log.info(
                    "Downloaded: %s (%.1f KB)",
                    save_path.name,
                    len(resp.content) / 1024,
                )
                return save_path
            except requests.RequestException as exc:
                log.warning(
                    "Download failed for %s (attempt %d/%d): %s",
                    file_info["name"],
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF * attempt)

        return None

# ── Windows Toast Notification ────────────────────────────────────────

def send_windows_notification(title: str, message: str):
    """Send a native Windows 10/11 toast notification as a bonus alert."""
    try:
        from ctypes import windll
        # Use PowerShell to send a toast (works on all Windows 10+)
        import subprocess
        ps_cmd = (
            f'[Windows.UI.Notifications.ToastNotificationManager, '
            f'Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; '
            f'$xml = [Windows.UI.Notifications.ToastNotificationManager]'
            f'::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]'
            f'::ToastText02); '
            f'$nodes = $xml.GetElementsByTagName("text"); '
            f'$nodes.Item(0).AppendChild($xml.CreateTextNode("{title}")); '
            f'$nodes.Item(1).AppendChild($xml.CreateTextNode("{message}")); '
            f'$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); '
            f'[Windows.UI.Notifications.ToastNotificationManager]'
            f'::CreateToastNotifier("{APP_NAME}").Show($toast)'
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception:
        pass  # notification is a bonus, don't crash

# ── Image Popup (Picture-in-Picture) ─────────────────────────────────

class ImagePopup:
    """
    Displays a borderless, always-on-top, auto-dismissing popup window
    positioned at a screen corner — like picture-in-picture.
    """

    POSITION_MAP = {
        "bottom-right": lambda sw, sh, ww, wh: (sw - ww - 20, sh - wh - 60),
        "bottom-left": lambda sw, sh, ww, wh: (20, sh - wh - 60),
        "top-right": lambda sw, sh, ww, wh: (sw - ww - 20, 40),
        "top-left": lambda sw, sh, ww, wh: (20, 40),
        "center": lambda sw, sh, ww, wh: ((sw - ww) // 2, (sh - wh) // 2),
    }

    TITLE_HEIGHT = 32
    PROGRESS_HEIGHT = 4
    BG_COLOR = "#1a1a2e"
    TITLE_BG = "#16213e"
    TITLE_FG = "#e2e2e2"
    ACCENT = "#e94560"

    def __init__(self, config: dict):
        popup_cfg = config["popup"]
        self.max_width = popup_cfg.get("max_width", 600)
        self.max_height = popup_cfg.get("max_height", 500)
        self.duration = popup_cfg.get("display_seconds", 30)
        self.opacity = popup_cfg.get("opacity", 0.95)
        self.position = popup_cfg.get("position", "bottom-right")

    def show(self, image_path: Path):
        """Show the image in a new PiP popup (runs in its own thread)."""
        thread = threading.Thread(
            target=self._build_and_show, args=(image_path,), daemon=True
        )
        thread.start()

    def _build_and_show(self, image_path: Path):
        try:
            root = tk.Tk()
            root.withdraw()

            # ── Load & resize image ──────────────────────────────
            img = Image.open(image_path)
            # Convert RGBA/palette to RGB for compatibility
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            img_max_h = self.max_height - self.TITLE_HEIGHT - self.PROGRESS_HEIGHT
            img.thumbnail((self.max_width, img_max_h), Image.LANCZOS)
            img_w, img_h = img.size
            tk_img = ImageTk.PhotoImage(img)

            win_w = img_w
            win_h = img_h + self.TITLE_HEIGHT + self.PROGRESS_HEIGHT

            # ── Window chrome ────────────────────────────────────
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.0)
            root.configure(bg=self.BG_COLOR)

            # ── Position ─────────────────────────────────────────
            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()
            pos_fn = self.POSITION_MAP.get(
                self.position, self.POSITION_MAP["bottom-right"]
            )
            x, y = pos_fn(screen_w, screen_h, win_w, win_h)
            root.geometry(f"{win_w}x{win_h}+{x}+{y}")

            # ── Title bar ────────────────────────────────────────
            title_frame = tk.Frame(
                root, bg=self.TITLE_BG, height=self.TITLE_HEIGHT
            )
            title_frame.pack(fill="x")
            title_frame.pack_propagate(False)

            # Try to parse date from filename (DD-MM-YYYY.ext)
            date_str = self._parse_date_from_filename(image_path.stem)
            if not date_str:
                date_str = datetime.now().strftime("%b %d, %Y")

            tk.Label(
                title_frame,
                text=f"  \u2600  {APP_NAME}  •  {date_str}",
                bg=self.TITLE_BG,
                fg=self.TITLE_FG,
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            close_btn = tk.Label(
                title_frame,
                text=" \u2715 ",
                bg=self.TITLE_BG,
                fg="#888",
                font=("Segoe UI", 10),
                cursor="hand2",
            )
            close_btn.pack(side="right", padx=(0, 4))
            close_btn.bind("<Button-1>", lambda _: root.destroy())
            close_btn.bind(
                "<Enter>", lambda _: close_btn.configure(fg=self.ACCENT)
            )
            close_btn.bind(
                "<Leave>", lambda _: close_btn.configure(fg="#888")
            )

            # ── Drag support on title bar ────────────────────────
            drag_data = {"x": 0, "y": 0}

            def start_drag(event):
                drag_data["x"] = event.x
                drag_data["y"] = event.y

            def do_drag(event):
                dx = event.x - drag_data["x"]
                dy = event.y - drag_data["y"]
                new_x = root.winfo_x() + dx
                new_y = root.winfo_y() + dy
                root.geometry(f"+{new_x}+{new_y}")

            title_frame.bind("<Button-1>", start_drag)
            title_frame.bind("<B1-Motion>", do_drag)

            # ── Image canvas ─────────────────────────────────────
            canvas = tk.Canvas(
                root,
                width=img_w,
                height=img_h,
                bg=self.BG_COLOR,
                highlightthickness=0,
            )
            canvas.pack()
            canvas.create_image(0, 0, anchor="nw", image=tk_img)
            canvas.bind("<Button-1>", lambda _: root.destroy())

            # ── Progress bar (auto-dismiss countdown) ────────────
            progress_canvas = tk.Canvas(
                root,
                width=win_w,
                height=self.PROGRESS_HEIGHT,
                bg=self.BG_COLOR,
                highlightthickness=0,
            )
            progress_canvas.pack(fill="x")
            progress_rect = progress_canvas.create_rectangle(
                0, 0, win_w, self.PROGRESS_HEIGHT, fill=self.ACCENT, outline=""
            )

            # ── Animations ───────────────────────────────────────
            root.deiconify()

            # Fade-in
            def fade_in(alpha=0.0):
                if alpha < self.opacity:
                    alpha = min(alpha + 0.05, self.opacity)
                    root.attributes("-alpha", alpha)
                    root.after(20, fade_in, alpha)
                else:
                    root.attributes("-alpha", self.opacity)

            fade_in()

            # Progress countdown
            start_time = time.time()
            total = self.duration

            def update_progress():
                elapsed = time.time() - start_time
                remaining = max(0, total - elapsed)
                fraction = remaining / total
                try:
                    progress_canvas.coords(
                        progress_rect,
                        0,
                        0,
                        win_w * fraction,
                        self.PROGRESS_HEIGHT,
                    )
                except tk.TclError:
                    return  # window already destroyed
                if remaining > 0:
                    root.after(100, update_progress)
                else:
                    fade_out()

            root.after(500, update_progress)  # start after fade-in

            # Fade-out then destroy
            def fade_out(alpha=None):
                if alpha is None:
                    alpha = self.opacity
                if alpha > 0:
                    alpha = max(alpha - 0.05, 0)
                    try:
                        root.attributes("-alpha", alpha)
                        root.after(20, fade_out, alpha)
                    except tk.TclError:
                        return
                else:
                    try:
                        root.destroy()
                    except tk.TclError:
                        pass

            root.mainloop()

        except Exception as exc:
            log.error("Popup error: %s", exc)

    @staticmethod
    def _parse_date_from_filename(stem: str) -> Optional[str]:
        """Try to parse DD-MM-YYYY from filename stem."""
        for fmt_in, fmt_out in [
            ("%d-%m-%Y", "%b %d, %Y"),  # 17-03-2026 → Mar 17, 2026
            ("%Y-%m-%d", "%b %d, %Y"),  # 2026-03-17 → Mar 17, 2026
            ("%d_%m_%Y", "%b %d, %Y"),  # 17_03_2026
            ("%Y_%m_%d", "%b %d, %Y"),  # 2026_03_17
        ]:
            try:
                dt = datetime.strptime(stem, fmt_in)
                return dt.strftime(fmt_out)
            except ValueError:
                continue
        return None

# ── System Tray Icon ─────────────────────────────────────────────────

def _create_tray_image() -> Image.Image:
    """Generate a simple sun icon for the system tray."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Sun body
    center, radius = size // 2, 16
    draw.ellipse(
        [center - radius, center - radius, center + radius, center + radius],
        fill="#FFA500",
    )

    # Rays
    ray_len = 10
    ray_start = radius + 3
    for angle_deg in range(0, 360, 45):
        angle = math.radians(angle_deg)
        x1 = center + ray_start * math.cos(angle)
        y1 = center + ray_start * math.sin(angle)
        x2 = center + (ray_start + ray_len) * math.cos(angle)
        y2 = center + (ray_start + ray_len) * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill="#FFA500", width=3)

    return img

# ── Main Bot ──────────────────────────────────────────────────────────

class MorningBot:
    """Orchestrates GitHub monitoring, popup display, and system tray."""

    def __init__(self):
        log.info("=== %s v%s starting ===", APP_NAME, APP_VERSION)
        log.info("Base directory: %s", BASE_DIR)
        log.info("Frozen (exe): %s", getattr(sys, "frozen", False))

        self.config = load_config()
        self.state = BotState()
        self.monitor = GitHubMonitor(self.config)
        self.popup = ImagePopup(self.config)
        self.running = False
        self.tray_icon: Optional[pystray.Icon] = None

        self.cache_dir = BASE_DIR / self.config["storage"]["image_cache_dir"]
        self.cache_dir.mkdir(exist_ok=True)

        self.poll_interval = self.config["polling"]["interval_seconds"]
        self._active_start = self.config["polling"]["active_hours"]["start"]
        self._active_end = self.config["polling"]["active_hours"]["end"]

    # ── lifecycle ─────────────────────────────────────────────────

    def start(self):
        self.running = True
        self._write_pid()
        self._register_signals()

        # Cache cleanup on start
        self._cleanup_cache()

        # Initial check
        threading.Thread(target=self._initial_check, daemon=True).start()

        # Start polling thread
        poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        poll_thread.start()

        # Start system tray (blocks main thread)
        self._run_tray()

    def stop(self):
        log.info("Shutting down …")
        self.running = False
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self._remove_pid()
        log.info("=== Stopped ===")

    # ── PID lock ──────────────────────────────────────────────────

    def _write_pid(self):
        existing_pid = self._read_pid()
        if existing_pid and self._is_process_running(existing_pid):
            log.error("Bot already running (PID %d). Exiting.", existing_pid)
            _show_error_popup(
                "Already Running",
                f"{APP_NAME} is already running (PID {existing_pid}).\n"
                "Check the system tray for the ☀ icon.",
            )
            sys.exit(1)
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        log.debug("PID file written: %d", os.getpid())

    @staticmethod
    def _read_pid() -> Optional[int]:
        if PID_FILE.exists():
            try:
                return int(PID_FILE.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                return None
        return None

    @staticmethod
    def _is_process_running(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    @staticmethod
    def _remove_pid():
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    # ── signals ───────────────────────────────────────────────────

    def _register_signals(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, lambda *_: self.stop())
            except (OSError, ValueError):
                pass

    # ── active hours ──────────────────────────────────────────────

    def _is_active_hours(self) -> bool:
        now = datetime.now().strftime("%H:%M")
        return self._active_start <= now <= self._active_end

    # ── polling ───────────────────────────────────────────────────

    def _initial_check(self):
        """Run first check shortly after startup."""
        time.sleep(5)
        log.info("Running initial check …")
        self._check_and_notify()

    def _poll_loop(self):
        """Background loop that checks GitHub at the configured interval."""
        while self.running:
            time.sleep(self.poll_interval)
            if not self.running:
                break
            if not self._is_active_hours():
                log.debug("Outside active hours — skipping poll")
                continue
            self._check_and_notify()

    def _check_and_notify(self):
        """Core logic: check GitHub → download new → show popup."""
        try:
            images = self.monitor.get_image_list()
            if images is None:
                return  # 304 or error

            new_images = self.state.get_new_images(images)
            if not new_images:
                log.debug("No new images detected")
                return

            log.info("%d new image(s) found", len(new_images))

            # Process all new images, show popup for the latest
            last_path = None
            for img_info in new_images:
                local_path = self.monitor.download_image(img_info, self.cache_dir)
                if local_path:
                    self.state.mark_seen(img_info, str(local_path))
                    last_path = local_path

            if last_path:
                log.info("Showing popup for: %s", last_path.name)
                self.popup.show(last_path)
                send_windows_notification(
                    "🌅 New Motivation!",
                    f"Today's image: {last_path.name}",
                )

        except Exception as exc:
            log.error("Check failed: %s", exc, exc_info=True)

    # ── tray commands ─────────────────────────────────────────────

    def _on_check_now(self, icon=None, item=None):
        log.info("Manual check requested")
        threading.Thread(target=self._check_and_notify, daemon=True).start()

    def _on_show_last(self, icon=None, item=None):
        if self.state.last_image and Path(self.state.last_image).exists():
            log.info("Showing last image: %s", self.state.last_image)
            self.popup.show(Path(self.state.last_image))
        else:
            log.info("No previous image to show")

    def _on_quit(self, icon=None, item=None):
        self.stop()

    # ── cache cleanup ─────────────────────────────────────────────

    def _cleanup_cache(self):
        """Remove cached images older than max_cache_days."""
        max_days = self.config["storage"]["max_cache_days"]
        cutoff = datetime.now() - timedelta(days=max_days)
        removed = 0
        try:
            for f in self.cache_dir.iterdir():
                if f.suffix.lower() in IMAGE_EXTENSIONS:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime < cutoff:
                        f.unlink()
                        removed += 1
            if removed:
                log.info("Cache cleanup: removed %d old image(s)", removed)
        except Exception as exc:
            log.warning("Cache cleanup error: %s", exc)

    # ── system tray ───────────────────────────────────────────────

    def _run_tray(self):
        """Create and run the system tray icon (blocks)."""
        menu = pystray.Menu(
            MenuItem("Check Now", self._on_check_now),
            MenuItem("Show Last Image", self._on_show_last),
            pystray.Menu.SEPARATOR,
            MenuItem("Quit", self._on_quit),
        )

        self.tray_icon = pystray.Icon(
            "morning_bot",
            icon=_create_tray_image(),
            title=f"{APP_NAME} v{APP_VERSION}",
            menu=menu,
        )

        log.info("System tray icon active — bot is running")
        self.tray_icon.run()

# ── CLI Entry Point ───────────────────────────────────────────────────

def main():
    if "--check-now" in sys.argv:
        config = load_config()
        state = BotState()
        monitor = GitHubMonitor(config)
        popup = ImagePopup(config)
        cache_dir = BASE_DIR / config["storage"]["image_cache_dir"]
        cache_dir.mkdir(exist_ok=True)

        log.info("One-shot check …")
        images = monitor.get_image_list()
        if images:
            new_imgs = state.get_new_images(images)
            if new_imgs:
                for img_info in new_imgs:
                    local = monitor.download_image(img_info, cache_dir)
                    if local:
                        state.mark_seen(img_info, str(local))
                        popup.show(local)
                        time.sleep(2)
            else:
                log.info("No new images")
        else:
            log.info("No images or not modified")
        time.sleep(5)
        return

    if "--show-last" in sys.argv:
        config = load_config()
        state = BotState()
        popup = ImagePopup(config)
        if state.last_image and Path(state.last_image).exists():
            popup.show(Path(state.last_image))
            time.sleep(config["popup"]["display_seconds"] + 3)
        else:
            log.info("No previous image to show")
        return

    # Normal start — run as tray bot
    bot = MorningBot()
    bot.start()


if __name__ == "__main__":
    main()
