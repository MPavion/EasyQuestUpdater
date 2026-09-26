#!/usr/bin/env python3
"""EasyQuestUpdater — Downloads and installs Meta Quest firmware via ADB sideload."""

import os
import sys
import json
import shutil
import socket
import subprocess
import threading
import time
import webbrowser
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QMetaObject
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit,
    QFileDialog, QMessageBox, QFrame,
)
from PyQt6.QtGui import QColor, QPalette

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

try:
    import websocket
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "websocket-client"], check=True)
    import websocket


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_NAME        = "EasyQuestUpdater"
CHUNK_SIZE      = 1 * 1024 * 1024
DEFAULT_OUT     = str(Path.home() / "Downloads" / "quest-firmware")
ADB_DL_URL      = "https://developer.android.com/tools/releases/platform-tools"
FIRMWARE_PAGE   = "https://www.meta.com/en-gb/help/quest/software_update/"
BROWSER_PROFILE = str(Path.home() / ".quest-updater-profile")

DISCLAIMER = (
    "⚠ EasyQuestUpdater installs firmware via ADB sideload. "
    "Use entirely at your own risk. The authors accept no responsibility "
    "for device damage, data loss, or warranty voidance."
)

STYLE = """
QMainWindow, QWidget#root { background: #1a1a2e; }
QLabel { color: #e0e0e0; background: transparent; }
QLabel#dim        { color: #7a8599; font-size: 10px; }
QLabel#header     { color: #e94560; font-size: 16px; font-weight: bold; }
QLabel#pct        { color: #e94560; font-size: 28px; font-weight: bold; }
QLabel#pct_sub    { color: #7a8599; font-size: 10px; }
QLabel#badge_ok   { background: #1a6b3a; color: white;   border-radius: 4px; padding: 3px 10px; font-size: 9px; }
QLabel#badge_err  { background: #6b1a1a; color: #ffaaaa; border-radius: 4px; padding: 3px 10px; font-size: 9px; }
QLabel#badge_wait { background: #2a2a3e; color: #7a8599; border-radius: 4px; padding: 3px 10px; font-size: 9px; }
QLabel#disclaimer { color: #3e4a5c; font-size: 9px; }
QFrame#adb_panel  { background: #16213e; border-radius: 6px; }
QLineEdit {
    background: #16213e; color: #e0e0e0; border: none;
    border-radius: 4px; padding: 7px 8px; font-size: 10px;
}
QLineEdit:focus { border: 1px solid #0f3460; }
QPushButton { border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; font-size: 10px; }
QPushButton#primary   { background: #e94560; color: white; }
QPushButton#primary:hover   { background: #c73652; }
QPushButton#primary:disabled { background: #5a2030; color: #888; }
QPushButton#capture   { background: #0f6e3a; color: white; }
QPushButton#capture:hover   { background: #0d8a49; }
QPushButton#capture:disabled { background: #1a3a2a; color: #555; }
QPushButton#secondary { background: #0f3460; color: #e0e0e0; }
QPushButton#secondary:hover { background: #1a4a80; }
QPushButton#ghost { background: #16213e; color: #7a8599; }
QPushButton#ghost:hover { background: #1f2d4e; color: #e0e0e0; }
QPushButton#icon_btn {
    background: transparent; color: #3a4a5c;
    border: none; padding: 2px 6px; font-size: 14px;
}
QPushButton#icon_btn:hover { color: #8a9abc; }
QProgressBar {
    background: #16213e; border: none; border-radius: 4px;
    height: 8px; text-align: center; color: transparent;
}
QProgressBar::chunk { background: #e94560; border-radius: 4px; }
QTextEdit {
    background: #16213e; color: #c8d0e0; border: none;
    border-radius: 4px; font-family: Consolas, monospace;
    font-size: 9px; padding: 6px;
}
QScrollBar:vertical { background: #16213e; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #0f3460; border-radius: 4px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


# ---------------------------------------------------------------------------
# Non-UI helpers
# ---------------------------------------------------------------------------

def _filename_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    return name if (name and "." in name) else "quest_firmware.zip"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def find_adb(hint: str | None = None) -> str | None:
    if hint:
        return hint if Path(hint).exists() else None
    try:
        r = subprocess.run(["adb", "version"], capture_output=True, timeout=5)
        if r.returncode == 0:
            return "adb"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    for p in [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/platform-tools/adb.exe",
        Path(os.environ.get("USERPROFILE", "")) / "AppData/Local/Android/Sdk/platform-tools/adb.exe",
        Path("C:/platform-tools/adb.exe"),
        Path("C:/Program Files/Android/platform-tools/adb.exe"),
    ]:
        if p.exists():
            return str(p)
    return None


def find_browser() -> str | None:
    for p in [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    ]:
        if p.exists():
            return str(p)
    return None


def _adb_devices(adb: str) -> list[str]:
    r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10)
    return [
        line.split("\t")[0]
        for line in r.stdout.strip().splitlines()[1:]
        if "\t" in line and line.split("\t")[1].strip() == "device"
    ]


# ---------------------------------------------------------------------------
# Worker: Browser URL capture via Chrome DevTools Protocol
# ---------------------------------------------------------------------------

class CaptureWorker(QObject):
    log       = pyqtSignal(str)
    captured  = pyqtSignal(str, dict)
    error     = pyqtSignal(str)

    LOG_BYTES = 1 * 1024 * 1024   # log any response over this size
    MIN_BYTES = 50 * 1024 * 1024  # capture as firmware if over this size

    def __init__(self, browser_path: str):
        super().__init__()
        self.browser_path = browser_path
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        port = _free_port()
        profile_dir = Path(BROWSER_PROFILE)
        profile_dir.mkdir(parents=True, exist_ok=True)

        self.log.emit("Launching browser…")
        try:
            subprocess.Popen([
                self.browser_path,
                f"--remote-debugging-port={port}",
                f"--remote-allow-origins=http://localhost:{port}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                FIRMWARE_PAGE,
            ])
        except Exception as exc:
            self.error.emit(f"Failed to launch browser: {exc}")
            return

        self.log.emit("Waiting for browser to start…")
        browser_ws_url = None
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self._stop:
                return
            try:
                r = requests.get(f"http://localhost:{port}/json/version", timeout=2)
                if r.status_code == 200:
                    browser_ws_url = r.json().get("webSocketDebuggerUrl")
                    if browser_ws_url:
                        break
            except Exception:
                pass
            time.sleep(0.5)

        if not browser_ws_url:
            self.error.emit("Browser did not start within 60 seconds.")
            return

        try:
            ws = websocket.create_connection(browser_ws_url, timeout=3)
        except Exception as exc:
            self.error.emit(f"Could not connect to browser debug port: {exc}")
            return

        ws.send(json.dumps({
            "id": 1,
            "method": "Target.setAutoAttach",
            "params": {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True},
        }))

        pending: dict[str, dict] = {}

        self.log.emit("Browser ready — the Meta firmware page is opening.")
        self.log.emit("─" * 44)
        self.log.emit("  1. Log in to Meta if prompted.")
        self.log.emit("  2. Connect your Quest headset via USB.")
        self.log.emit("  3. Click  Start Download  on the page.")
        self.log.emit("     The URL will be captured automatically.")
        self.log.emit("─" * 44)

        while not self._stop:
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                break

            try:
                msg = json.loads(raw)
            except Exception:
                continue

            method     = msg.get("method", "")
            session_id = msg.get("sessionId", "")
            params     = msg.get("params", {})

            if method == "Target.attachedToTarget":
                new_sid = params.get("sessionId", "")
                if params.get("targetInfo", {}).get("type") == "page" and new_sid:
                    ws.send(json.dumps({"id": 10, "sessionId": new_sid, "method": "Network.enable", "params": {}}))
                    ws.send(json.dumps({"id": 11, "sessionId": new_sid, "method": "Page.enable", "params": {}}))
                    ws.send(json.dumps({"id": 12, "sessionId": new_sid, "method": "Page.setDownloadBehavior", "params": {"behavior": "allow"}}))

            elif method == "Page.downloadWillBegin" and session_id:
                dl_url  = params.get("url", "")
                dl_name = params.get("suggestedFilename", "")
                if dl_url.startswith("http"):
                    hdrs = {}
                    for key, info in pending.items():
                        if key.startswith(session_id + ":"):
                            stored = info.get("url", "")
                            if stored and stored.split("?")[0] == dl_url.split("?")[0]:
                                hdrs = info.get("headers", {})
                                break
                    self.log.emit(f"Download intercepted! {dl_name or dl_url[:80]}")
                    ws.close()
                    self.captured.emit(dl_url, hdrs)
                    return

            elif method == "Network.requestWillBeSent" and session_id:
                req_id  = params.get("requestId", "")
                request = params.get("request", {})
                pending[f"{session_id}:{req_id}"] = {
                    "url":     request.get("url", ""),
                    "headers": request.get("headers", {}),
                }

            elif method == "Network.responseReceived" and session_id:
                req_id    = params.get("requestId", "")
                response  = params.get("response", {})
                resp_hdrs = {k.lower(): v for k, v in response.get("headers", {}).items()}

                content_length = int(resp_hdrs.get("content-length", 0))
                mime           = response.get("mimeType", "")
                status         = response.get("status", 0)
                disposition    = resp_hdrs.get("content-disposition", "")

                is_large   = content_length >= self.MIN_BYTES
                is_binary  = any(t in mime for t in ("octet-stream", "zip", "binary", "x-zip", "download"))
                is_attach  = "attachment" in disposition.lower()
                is_success = status in (200, 206)
                info       = pending.get(f"{session_id}:{req_id}")
                req_url    = (info or {}).get("url", "") or response.get("url", "")
                is_fw_ext  = any(req_url.lower().endswith(e)
                                 for e in (".zip", ".bin", ".apk", ".img", ".tar", ".gz", ".obb"))

                if content_length >= self.LOG_BYTES or is_binary or is_attach:
                    size_str = f"{content_length/1024**2:.1f} MB" if content_length else "no content-length"
                    self.log.emit(
                        f"Response {status}: {mime or '(no mime)'}  {size_str}"
                        + (f"  [attachment]" if is_attach else "")
                        + (f"  {req_url[:80]}" if req_url else "")
                    )

                if is_success and (is_large or is_binary or is_attach or is_fw_ext):
                    if req_url.startswith("http"):
                        size_str = (f"{content_length/1024**3:.2f} GB"
                                    if content_length else "size unknown")
                        self.log.emit(f"Download captured! ({size_str})")
                        ws.close()
                        self.captured.emit(req_url, (info or {}).get("headers", {}))
                        return

        ws.close()


# ---------------------------------------------------------------------------
# Worker: Download
# ---------------------------------------------------------------------------

class DownloadWorker(QObject):
    log         = pyqtSignal(str)
    progress    = pyqtSignal(int, int, float)
    finished    = pyqtSignal(str)
    interrupted = pyqtSignal()
    error       = pyqtSignal(str)

    def __init__(self, url: str, output_dir: Path, extra_headers: dict | None = None):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.extra_headers = extra_headers or {}

    def run(self):
        self.log.emit("Download thread started.")
        url, output_dir = self.url, self.output_dir
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            filename      = _filename_from_url(url)
            final_path    = output_dir / filename
            partial_path  = output_dir / (filename + ".partial")
            progress_file = output_dir / (filename + ".progress")

            resume_from = 0
            if partial_path.exists():
                resume_from = partial_path.stat().st_size
                if resume_from > 0:
                    self.log.emit(
                        f"Partial download found — resuming from "
                        f"{resume_from/1024**3:.2f} GB ({resume_from/1024**2:.0f} MB)…"
                    )

            if final_path.exists() and not partial_path.exists():
                self.log.emit(f"Already downloaded: {final_path}")
                self.finished.emit(str(final_path))
                return

            KEEP  = {"cookie", "authorization", "x-auth-token"}
            STRIP = {
                "range", "accept-encoding", "if-none-match", "if-modified-since",
                "if-range", "content-length", "content-type", "transfer-encoding",
                "connection", "host", "origin", "referer",
                "upgrade-insecure-requests", "sec-fetch-dest", "sec-fetch-mode",
                "sec-fetch-site", "sec-fetch-user", "sec-ch-ua", "sec-ch-ua-mobile",
                "sec-ch-ua-platform",
            }
            headers = {
                k: v for k, v in self.extra_headers.items()
                if k.lower() in KEEP or k.lower() not in STRIP
            }
            if resume_from:
                headers["Range"] = f"bytes={resume_from}-"

            kept = [k for k in headers if k.lower() != "cookie"]
            parsed_host = urlparse(url).netloc
            self.log.emit(f"Connecting to {parsed_host}…  (headers: {', '.join(kept) or 'none'})")

            resp = requests.get(url, headers=headers, stream=True, timeout=(15, 60))

            if resp.status_code == 416:
                if partial_path.exists():
                    partial_path.rename(final_path)
                    progress_file.unlink(missing_ok=True)
                    self.log.emit("File already fully downloaded.")
                    self.finished.emit(str(final_path))
                    return
                self.error.emit("HTTP 416: server rejected the range request.")
                return

            if resp.status_code not in (200, 206):
                self.error.emit(
                    f"HTTP {resp.status_code}: {resp.reason}\n\n"
                    "The URL may have expired — re-capture it from the browser."
                )
                return

            if resume_from and resp.status_code == 200:
                self.log.emit("Server does not support resume — restarting.")
                resume_from = 0
                partial_path.unlink(missing_ok=True)

            content_length = int(resp.headers.get("Content-Length", 0))
            total = content_length + (resume_from if resp.status_code == 206 else 0)
            progress_file.write_text(json.dumps({"url": url, "total": total}))

            self.log.emit(f"Connected — HTTP {resp.status_code}")
            self.log.emit(f"File: {filename}")
            if total:
                self.log.emit(f"Size: {total/1024**3:.2f} GB")
            else:
                self.log.emit("Size: unknown (server did not send Content-Length)")

            # Disk space check — need at least the bytes still to download + 200 MB headroom
            already_have = resume_from if resp.status_code == 206 else 0
            still_needed = (total - already_have) if total else 2 * 1024 ** 3
            free_bytes   = shutil.disk_usage(output_dir).free
            if free_bytes < still_needed + 200 * 1024 ** 2:
                self.error.emit(
                    f"Not enough disk space.\n\n"
                    f"Need:      {still_needed / 1024**3:.2f} GB\n"
                    f"Available: {free_bytes / 1024**3:.2f} GB\n\n"
                    f"Free up space on this drive and try again."
                )
                return

            self.log.emit("Downloading — will resume if interrupted.")

            downloaded = resume_from
            mode = "ab" if resume_from else "wb"
            last_t, last_b = time.monotonic(), resume_from

            with open(partial_path, mode) as fh:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    downloaded += len(chunk)
                    now     = time.monotonic()
                    elapsed = now - last_t
                    speed   = (downloaded - last_b) / elapsed if elapsed >= 0.5 else 0
                    if elapsed >= 0.5:
                        last_t, last_b = now, downloaded
                    self.progress.emit(downloaded, total, speed)

            # ── Validate before finalising ────────────────────────────────
            self.log.emit("Validating download…")
            actual = partial_path.stat().st_size
            if total and actual != total:
                self.error.emit(
                    f"File size mismatch after download.\n\n"
                    f"Expected: {total:,} bytes\n"
                    f"Got:      {actual:,} bytes\n\n"
                    "The file may be corrupt. Click Download Firmware to try again."
                )
                return

            if filename.lower().endswith(".zip"):
                self.log.emit("Checking ZIP integrity — this may take a minute…")
                try:
                    with zipfile.ZipFile(partial_path) as zf:
                        bad = zf.testzip()
                    if bad:
                        self.error.emit(
                            f"ZIP integrity check failed — first bad file: {bad}\n\n"
                            "The download appears corrupt. Click Download Firmware to try again."
                        )
                        return
                except zipfile.BadZipFile as exc:
                    self.error.emit(
                        f"Downloaded file is not a valid ZIP archive: {exc}\n\n"
                        "Click Download Firmware to try again."
                    )
                    return

            self.log.emit("Validation passed ✓")
            partial_path.rename(final_path)
            progress_file.unlink(missing_ok=True)
            self.log.emit("Download complete!")
            self.log.emit(f"Saved to: {final_path}")
            self.finished.emit(str(final_path))

        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError) as exc:
            self.log.emit(f"Connection lost: {exc}")
            self.log.emit("Click  Download Firmware  to resume.")
            self.interrupted.emit()
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Worker: Install
# ---------------------------------------------------------------------------

class InstallWorker(QObject):
    log      = pyqtSignal(str)
    finished = pyqtSignal()
    aborted  = pyqtSignal()
    error    = pyqtSignal(str)
    need_ok  = pyqtSignal()
    user_ok    = False
    _cancelled = False

    def __init__(self, adb: str, firmware_path: Path):
        super().__init__()
        self.adb = adb
        self.firmware_path = firmware_path

    def run(self):
        adb, fw = self.adb, self.firmware_path
        try:
            devices = _adb_devices(adb)
            if not devices:
                self.error.emit(
                    "No Quest headset detected over USB.\n\n"
                    "Checklist:\n"
                    "  • USB cable is plugged in\n"
                    "  • Developer Mode is ON\n"
                    "    (Meta Quest app → headset → Developer Mode)\n"
                    "  • Inside the headset: accept ‘Allow USB Debugging’\n"
                    "  • USB connection mode: File Transfer / MTP"
                )
                self.aborted.emit()
                return

            serial = devices[0]
            self.log.emit(f"Headset connected: {serial}")
            self.log.emit(f"Firmware: {fw.name}  ({fw.stat().st_size/1024**3:.2f} GB)")
            self.log.emit("Rebooting into recovery mode…")
            subprocess.run([adb, "-s", serial, "reboot", "recovery"], timeout=15)

            self.user_ok   = False
            self._cancelled = False
            self.need_ok.emit()
            deadline = time.monotonic() + 180
            while not self.user_ok and not self._cancelled and time.monotonic() < deadline:
                time.sleep(0.25)
            if self._cancelled or not self.user_ok:
                self.log.emit("Installation cancelled.")
                self.aborted.emit()
                return

            self.log.emit("Waiting for sideload mode…")
            deadline = time.monotonic() + 90
            ready = False
            while time.monotonic() < deadline:
                r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10)
                if "sideload" in r.stdout:
                    ready = True
                    break
                time.sleep(3)

            if not ready:
                self.error.emit(
                    "Headset did not enter sideload mode within 90 seconds.\n"
                    "Make sure you selected ‘Apply update from ADB’ on the headset."
                )
                self.aborted.emit()
                return

            self.log.emit("Sideload mode detected — transferring firmware…")
            self.log.emit("Do NOT disconnect the USB cable.")
            self.log.emit("This will take approximately 10–20 minutes.")

            result = subprocess.run([adb, "sideload", str(fw)], timeout=1800)

            if result.returncode == 0:
                self.log.emit("Sideload complete!")
                self.log.emit("The headset will reboot automatically.")
                self.log.emit("If it stays on recovery, select ‘Reboot system now’.")
                self.finished.emit()
            else:
                self.error.emit(
                    f"ADB sideload exited with code {result.returncode}.\n"
                    "Check the headset screen for an error message."
                )
                self.aborted.emit()

        except subprocess.TimeoutExpired:
            self.error.emit("ADB timed out. Check the USB connection.")
            self.aborted.emit()
        except Exception as exc:
            self.error.emit(str(exc))
            self.aborted.emit()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setFixedWidth(660)

        self._firmware_path:    Path | None = None
        self._adb:              str  | None = None
        self._captured_url:     str         = ""
        self._captured_headers: dict        = {}
        self._cap_worker:  CaptureWorker | None = None
        self._cap_thread:  QThread       | None = None
        self._dl_worker:   DownloadWorker | None = None
        self._inst_worker: InstallWorker  | None = None

        self._build_ui()
        self._init_log_file()
        self._check_partial()
        self._check_adb()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("header")
        hdr.addWidget(title)
        hdr.addStretch()

        gear_btn = QPushButton("⚙")
        gear_btn.setObjectName("icon_btn")
        gear_btn.setToolTip("Settings — change save folder")
        gear_btn.clicked.connect(self._toggle_settings)
        hdr.addWidget(gear_btn)

        self._badge = QLabel("ADB: checking…")
        self._badge.setObjectName("badge_wait")
        hdr.addWidget(self._badge)
        outer.addLayout(hdr)
        outer.addSpacing(14)

        # ── ADB setup panel (visible only when ADB is missing) ────────────
        self._adb_panel = QFrame()
        self._adb_panel.setObjectName("adb_panel")
        self._adb_panel.setVisible(False)
        adb_lay = QVBoxLayout(self._adb_panel)
        adb_lay.setContentsMargins(16, 12, 16, 14)
        adb_lay.setSpacing(8)

        warn_head = QLabel("⚠ ADB not found — required to install firmware onto your Quest")
        warn_head.setStyleSheet(
            "color: #ffaa44; font-size: 11px; font-weight: bold; background: transparent;"
        )
        adb_lay.addWidget(warn_head)

        steps_lbl = QLabel(
            "To set up ADB:\n"
            "  1.  Click  Download ADB  below.\n"
            "  2.  Extract the ZIP to  C:\\platform-tools\n"
            "  3.  Click  Check Again  — the badge above turns green.\n\n"
            "Also enable Developer Mode on your Quest headset before connecting:\n"
            "  Meta Quest mobile app  →  select headset  →  Developer Mode  →  toggle ON"
        )
        steps_lbl.setStyleSheet("color: #8aa0bc; font-size: 10px; background: transparent;")
        adb_lay.addWidget(steps_lbl)

        adb_btns = QHBoxLayout()
        dl_adb_btn = QPushButton("  Download ADB  ")
        dl_adb_btn.setObjectName("secondary")
        dl_adb_btn.clicked.connect(lambda: webbrowser.open(ADB_DL_URL))
        adb_btns.addWidget(dl_adb_btn)

        recheck_btn = QPushButton("  Check Again  ")
        recheck_btn.setObjectName("secondary")
        recheck_btn.clicked.connect(self._check_adb_again)
        adb_btns.addWidget(recheck_btn)
        adb_btns.addStretch()
        adb_lay.addLayout(adb_btns)

        outer.addWidget(self._adb_panel)

        # ── Settings panel (hidden, toggle via gear icon) ─────────────────
        self._settings_panel = QFrame()
        self._settings_panel.setVisible(False)
        sp_lay = QHBoxLayout(self._settings_panel)
        sp_lay.setContentsMargins(0, 8, 0, 0)
        sp_lay.setSpacing(6)
        sp_lay.addWidget(self._dim_label("Save to:"))
        self._dir_edit = QLineEdit(DEFAULT_OUT)
        sp_lay.addWidget(self._dir_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("ghost")
        browse_btn.setFixedWidth(62)
        browse_btn.clicked.connect(self._browse_dir)
        sp_lay.addWidget(browse_btn)
        outer.addWidget(self._settings_panel)
        outer.addSpacing(14)

        # ── Step 1: Capture ───────────────────────────────────────────────
        outer.addWidget(self._dim_label("Step 1 — Open the Meta firmware page and capture the download URL"))
        outer.addSpacing(4)

        cap_row = QHBoxLayout()
        cap_row.setSpacing(8)
        self._cap_btn = QPushButton("  Open Browser & Capture URL  ")
        self._cap_btn.setObjectName("capture")
        self._cap_btn.setFixedHeight(40)
        self._cap_btn.setToolTip(
            "Opens Chrome or Edge on the Meta firmware page.\n"
            "Log in, connect your Quest, click Start Download —\n"
            "the URL is captured automatically. Click again to stop."
        )
        self._cap_btn.clicked.connect(self._on_capture_toggle)
        cap_row.addWidget(self._cap_btn)
        self._cap_status = QLabel("Not captured yet")
        self._cap_status.setObjectName("dim")
        cap_row.addWidget(self._cap_status, 1)
        outer.addLayout(cap_row)
        outer.addSpacing(18)

        # ── Progress ──────────────────────────────────────────────────────
        pct_row = QHBoxLayout()
        self._pct_label = QLabel("—")
        self._pct_label.setObjectName("pct")
        pct_row.addWidget(self._pct_label)
        pct_row.addStretch()
        sub_col = QVBoxLayout()
        sub_col.setSpacing(2)
        sub_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._prog_label  = QLabel("")
        self._prog_label.setObjectName("pct_sub")
        self._prog_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._speed_label = QLabel("")
        self._speed_label.setObjectName("pct_sub")
        self._speed_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        sub_col.addWidget(self._prog_label)
        sub_col.addWidget(self._speed_label)
        pct_row.addLayout(sub_col)
        outer.addLayout(pct_row)
        outer.addSpacing(6)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setFixedHeight(12)
        self._progress.setTextVisible(False)
        outer.addWidget(self._progress)
        outer.addSpacing(16)

        # ── Step 2: Download & install ────────────────────────────────────
        outer.addWidget(self._dim_label("Step 2 — Download & install firmware"))
        outer.addSpacing(6)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._dl_btn = QPushButton("  Download Firmware  ")
        self._dl_btn.setObjectName("primary")
        self._dl_btn.setFixedHeight(40)
        self._dl_btn.setEnabled(False)
        self._dl_btn.clicked.connect(self._on_download)
        btn_row.addWidget(self._dl_btn)

        self._inst_btn = QPushButton("  Install via ADB  ")
        self._inst_btn.setObjectName("primary")
        self._inst_btn.setFixedHeight(40)
        self._inst_btn.setEnabled(False)
        self._inst_btn.clicked.connect(self._on_install)
        btn_row.addWidget(self._inst_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)
        outer.addSpacing(14)

        # ── Log ───────────────────────────────────────────────────────────
        outer.addWidget(self._dim_label("Log"))
        outer.addSpacing(4)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(160)
        outer.addWidget(self._log)
        outer.addSpacing(12)

        # ── Disclaimer ────────────────────────────────────────────────────
        disc = QLabel(DISCLAIMER)
        disc.setObjectName("disclaimer")
        disc.setWordWrap(True)
        disc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(disc)

        self.adjustSize()

    def _dim_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("dim")
        return lbl

    # ------------------------------------------------------------------
    # Settings toggle
    # ------------------------------------------------------------------

    def _toggle_settings(self):
        self._settings_panel.setVisible(not self._settings_panel.isVisible())
        self.adjustSize()

    # ------------------------------------------------------------------
    # Partial download check at startup
    # ------------------------------------------------------------------

    def _check_partial(self):
        self._log_line("Checking for downloads…")
        output_dir = Path(self._dir_edit.text())
        if not output_dir.exists():
            self._log_line("  None found.")
            return

        # ── Completed firmware files ──────────────────────────────────────
        fw_exts = {".zip", ".bin", ".img", ".apk"}
        completed = sorted(
            [p for p in output_dir.iterdir()
             if p.suffix.lower() in fw_exts
             and not p.name.endswith(".partial")
             and p.stat().st_size > 100 * 1024 * 1024],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if completed:
            fw = completed[0]
            size_gb = fw.stat().st_size / 1024**3
            self._firmware_path = fw
            self._inst_btn.setEnabled(True)
            self._progress.setRange(0, 1000)
            self._progress.setValue(1000)
            self._pct_label.setText("100%")
            self._prog_label.setText("Download complete")
            self._log_line("─" * 44)
            self._log_line(f"  Firmware ready: {fw.name}  ({size_gb:.2f} GB)")
            self._log_line("  Click  Install via ADB  to install it.")
            self._log_line("─" * 44)
            return

        # ── Incomplete / partial downloads ────────────────────────────────
        partials = sorted(
            output_dir.glob("*.partial"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not partials:
            self._log_line("  None found.")
            return

        partial    = partials[0]
        downloaded = partial.stat().st_size
        if downloaded == 0:
            self._log_line("  None found.")
            return

        filename      = partial.name.removesuffix(".partial")
        progress_file = output_dir / (filename + ".progress")

        total = 0
        if progress_file.exists():
            try:
                total = json.loads(progress_file.read_text()).get("total", 0)
            except Exception:
                pass

        self._log_line("─" * 44)
        self._log_line(f"  Incomplete download found: {filename}")
        if total:
            pct = min(downloaded / total * 100, 99.9)
            self._pct_label.setText(f"{pct:.0f}%")
            self._progress.setValue(int(pct * 10))
            self._prog_label.setText(f"{downloaded/1024**3:.2f} / {total/1024**3:.2f} GB")
            self._log_line(f"  {pct:.0f}% complete  ({downloaded/1024**3:.2f} / {total/1024**3:.2f} GB)")
        else:
            self._log_line(f"  {downloaded/1024**3:.2f} GB downloaded so far")

        self._cap_status.setText(f"Resume ready: {filename}")
        self._log_line("  Capture a new URL above to resume from where it stopped.")
        self._log_line("─" * 44)

    # ------------------------------------------------------------------
    # ADB check
    # ------------------------------------------------------------------

    def _check_adb(self):
        def _run():
            adb = find_adb()
            self._adb = adb
            QMetaObject.invokeMethod(self, "_on_adb_result", Qt.ConnectionType.QueuedConnection)
        threading.Thread(target=_run, daemon=True).start()

    def _check_adb_again(self):
        self._badge.setObjectName("badge_wait")
        self._badge.setText("ADB: checking…")
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._check_adb()

    def _on_adb_result(self):
        if self._adb:
            self._badge.setObjectName("badge_ok")
            self._badge.setText("ADB: ready")
            self._adb_panel.setVisible(False)
            self._log_line(f"ADB found: {self._adb}")
        else:
            self._badge.setObjectName("badge_err")
            self._badge.setText("ADB: not found")
            self._adb_panel.setVisible(True)
            self._log_line("ADB not found — see the setup panel above.")
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._log_line("Click ‘Open Browser & Capture URL’ to begin.")
        self.adjustSize()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _init_log_file(self):
        log_dir = Path(self._dir_edit.text())
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            log_dir = Path.home() / "Downloads"
        self._log_file = log_dir / "quest_updater.log"
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 52}\n")
                f.write(f"Session  {time.strftime('%Y-%m-%d  %H:%M:%S')}\n")
                f.write(f"{'=' * 52}\n")
        except Exception:
            self._log_file = None
        if self._log_file:
            self._log.append(f"Live log: {self._log_file}")

    def _log_line(self, msg: str):
        self._log.append(msg)
        if getattr(self, "_log_file", None):
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            except Exception:
                pass

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select save folder", self._dir_edit.text() or str(Path.home())
        )
        if d:
            self._dir_edit.setText(d)

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def _on_capture_toggle(self):
        if self._cap_worker is not None:
            self._stop_capture()
        else:
            self._on_capture()

    def _on_capture(self):
        browser = find_browser()
        if not browser:
            QMessageBox.critical(
                self, "Browser not found",
                "Chrome or Edge was not found on this PC.\n\n"
                "Install one and try again."
            )
            return

        self._cap_btn.setText("  Stop Listening  ")
        self._cap_status.setText("Listening — waiting for Start Download…")
        self._log_line(f"Browser: {browser}")

        worker = CaptureWorker(browser)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.log.connect(self._log_line)
        worker.captured.connect(self._on_captured)
        worker.error.connect(self._on_capture_error)
        worker.captured.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(self._on_capture_thread_done)

        self._cap_worker = worker
        self._cap_thread = thread
        thread.start()

    def _stop_capture(self):
        if self._cap_worker:
            self._cap_worker.stop()
        self._cap_worker = None
        self._cap_btn.setText("  Open Browser & Capture URL  ")
        self._cap_status.setText("Stopped")

    def _on_capture_thread_done(self):
        self._cap_worker = None
        self._cap_btn.setText("  Open Browser & Capture URL  ")

    def _on_captured(self, url: str, headers: dict):
        self._captured_url     = url
        self._captured_headers = headers
        self._cap_status.setText("URL captured")
        self._dl_btn.setEnabled(True)
        self._log_line("─" * 44)
        self._log_line("URL captured — download starting in this app.")
        self._log_line("You can now close the browser, or cancel /")
        self._log_line("pause its download — this app has taken over.")
        self._log_line("─" * 44)
        self._start_download(url, headers)

    def _on_capture_error(self, msg: str):
        self._cap_status.setText("Capture failed")
        QMessageBox.critical(self, "Capture Error", msg)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _on_download(self):
        if not self._captured_url:
            return
        self._start_download(self._captured_url, self._captured_headers)

    def _start_download(self, url: str, headers: dict):
        self._dl_btn.setEnabled(False)
        self._progress.setRange(0, 0)
        self._pct_label.setText("…")
        self._prog_label.setText("Connecting…")
        self._speed_label.setText("")

        worker = DownloadWorker(url, Path(self._dir_edit.text()), headers)
        worker.log.connect(self._log_line)
        worker.progress.connect(self._on_dl_progress)
        worker.finished.connect(self._on_dl_done)
        worker.interrupted.connect(self._on_dl_interrupted)
        worker.error.connect(self._on_dl_error)

        self._dl_worker = worker
        threading.Thread(target=worker.run, daemon=True).start()

    def _on_dl_progress(self, current: int, total: int, speed: float):
        if total:
            if self._progress.maximum() == 0:
                self._progress.setRange(0, 1000)
            pct = current / total * 100
            self._progress.setValue(int(pct * 10))
            self._pct_label.setText(f"{pct:.0f}%")
            self._prog_label.setText(f"{current/1024**3:.2f} / {total/1024**3:.2f} GB")
        else:
            mb = current / 1024**2
            self._pct_label.setText(f"{mb/1024:.2f} GB" if mb >= 1024 else f"{mb:.0f} MB")
            self._prog_label.setText("downloading (size unknown)")
        if speed > 0:
            unit, div = ("MB/s", 1024**2) if speed >= 1024**2 else ("KB/s", 1024)
            self._speed_label.setText(f"{speed/div:.1f} {unit}")

    def _on_dl_done(self, path: str):
        self._firmware_path = Path(path)
        self._dl_btn.setEnabled(True)
        self._inst_btn.setEnabled(True)
        self._progress.setRange(0, 1000)
        self._progress.setValue(1000)
        self._pct_label.setText("100%")
        self._prog_label.setText("Download complete")
        self._speed_label.setText("")

    def _on_dl_interrupted(self):
        self._dl_btn.setEnabled(True)
        self._prog_label.setText("Interrupted — click Download to resume")

    def _on_dl_error(self, msg: str):
        self._dl_btn.setEnabled(True)
        self._log_line(f"Download error: {msg[:300]}")
        QMessageBox.critical(self, "Download Error", msg)

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    def _on_install(self):
        if not self._firmware_path:
            return
        adb = find_adb()
        if not adb:
            QMessageBox.critical(
                self, "ADB not found",
                "ADB is required for installation.\n\n"
                "Download Platform Tools from the link in the setup panel,\n"
                "extract to C:\\platform-tools, then click Check Again."
            )
            return
        self._adb = adb
        self._badge.setObjectName("badge_ok")
        self._badge.setText("ADB: ready")
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._inst_btn.setEnabled(False)

        worker = InstallWorker(adb, self._firmware_path)
        worker.log.connect(self._log_line)
        worker.need_ok.connect(self._show_recovery_dialog)
        worker.finished.connect(self._on_inst_done)
        worker.aborted.connect(self._on_inst_aborted)
        worker.error.connect(self._on_inst_error)

        self._inst_worker = worker
        threading.Thread(target=worker.run, daemon=True).start()

    def _show_recovery_dialog(self):
        ok = QMessageBox.question(
            self,
            "Recovery Menu — Action Required",
            "The headset is rebooting into recovery mode.\n\n"
            "You may see a black screen saying  ‘No command’  — this is normal.\n"
            "If so:  hold the POWER button, then press VOLUME UP once.\n"
            "The full recovery menu will appear.\n\n"
            "In the recovery menu:\n\n"
            "  1.  Use the VOLUME buttons to scroll to\n"
            "       ‘Apply update from ADB’\n\n"
            "  2.  Press the POWER button to select it.\n\n"
            "The screen will then say:\n"
            "  ‘Now send the package via ADB sideload…’\n\n"
            "Click OK once you see that, or Cancel to abort.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if ok == QMessageBox.StandardButton.Ok:
            self._inst_worker.user_ok = True
        else:
            self._inst_worker._cancelled = True

    def _on_inst_done(self):
        self._progress.setValue(1000)
        self._pct_label.setText("Done")
        self._prog_label.setText("Firmware installed successfully")

    def _on_inst_aborted(self):
        if self._firmware_path:
            self._inst_btn.setEnabled(True)

    def _on_inst_error(self, msg: str):
        if self._firmware_path:
            self._inst_btn.setEnabled(True)
        QMessageBox.critical(self, "Install Error", msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor("#1a1a2e"))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Base,            QColor("#16213e"))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#1f2d4e"))
    palette.setColor(QPalette.ColorRole.Text,            QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Button,          QColor("#0f3460"))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#e0e0e0"))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor("#e94560"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
