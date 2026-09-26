#!/usr/bin/env python3
"""
Quest Firmware Updater
Downloads Meta Quest firmware with resume support and installs via ADB sideload.
"""

import os
import sys
import json
import subprocess
import argparse
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("Missing dependencies. Run:  pip install requests tqdm")
    sys.exit(1)


CHUNK_SIZE = 1024 * 1024  # 1 MB per write


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def _progress_path(partial: Path) -> Path:
    return partial.with_suffix(".progress")


def _load_progress(partial: Path) -> dict:
    p = _progress_path(partial)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_progress(partial: Path, data: dict):
    _progress_path(partial).write_text(json.dumps(data), encoding="utf-8")


def _filename_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    return name if name and "." in name else "quest_firmware.zip"


def download_firmware(url: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = _filename_from_url(url)
    final_path = output_dir / filename
    partial_path = output_dir / (filename + ".partial")

    progress = _load_progress(partial_path)
    resume_from = 0

    if partial_path.exists() and progress.get("url") == url:
        resume_from = partial_path.stat().st_size
        print(f"Resuming from {resume_from / 1024**2:.1f} MB...")
    elif final_path.exists():
        print(f"File already exists: {final_path}")
        if input("Re-download? [y/N] ").strip().lower() != "y":
            return final_path
        final_path.unlink()

    headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}

    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
    except requests.exceptions.ConnectionError as exc:
        sys.exit(f"Connection failed: {exc}")

    if resp.status_code == 416:
        # Server says the range is beyond EOF — treat as already complete
        if partial_path.exists():
            partial_path.rename(final_path)
            _progress_path(partial_path).unlink(missing_ok=True)
            return final_path
        sys.exit("HTTP 416: server rejected the range request and no partial file exists.")

    if resp.status_code not in (200, 206):
        sys.exit(f"HTTP {resp.status_code}: {resp.reason}")

    if resume_from and resp.status_code == 200:
        # Server ignored our Range header — restart
        print("Server does not support resume; restarting from the beginning.")
        resume_from = 0
        partial_path.unlink(missing_ok=True)

    content_length = int(resp.headers.get("Content-Length", 0))
    total_size = content_length + (resume_from if resp.status_code == 206 else 0)
    _save_progress(partial_path, {"url": url, "total": total_size})

    print(f"\nDownloading: {filename}")
    if total_size:
        print(f"Total size : {total_size / 1024**3:.2f} GB")

    mode = "ab" if resume_from else "wb"
    with open(partial_path, mode) as fh:
        with tqdm(
            total=total_size or None,
            initial=resume_from,
            unit="B", unit_scale=True, unit_divisor=1024,
            desc=filename, dynamic_ncols=True,
        ) as bar:
            try:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        fh.write(chunk)
                        bar.update(len(chunk))
            except (requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ConnectionError) as exc:
                print(f"\nDownload interrupted: {exc}")
                print("Progress saved — re-run the same command to resume.")
                sys.exit(1)

    partial_path.rename(final_path)
    _progress_path(partial_path).unlink(missing_ok=True)
    print(f"\nDownload complete: {final_path}")
    return final_path


# ---------------------------------------------------------------------------
# ADB helpers
# ---------------------------------------------------------------------------

def find_adb(hint: str | None = None) -> str | None:
    if hint:
        return hint if Path(hint).exists() else None

    # Try PATH first
    try:
        r = subprocess.run(["adb", "version"], capture_output=True, timeout=5)
        if r.returncode == 0:
            return "adb"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/platform-tools/adb.exe",
        Path(os.environ.get("USERPROFILE", "")) / "AppData/Local/Android/Sdk/platform-tools/adb.exe",
        Path("C:/platform-tools/adb.exe"),
        Path("C:/Program Files/Android/platform-tools/adb.exe"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)

    return None


def _adb_devices(adb: str) -> list[str]:
    r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10)
    serials = []
    for line in r.stdout.strip().splitlines()[1:]:
        if "\t" in line:
            serial, state = line.split("\t", 1)
            if state.strip() == "device":
                serials.append(serial.strip())
    return serials


def _wait_for_sideload(adb: str, timeout: int = 90) -> bool:
    print("Waiting for device to enter sideload mode", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10)
        if "sideload" in r.stdout:
            print(" ready!")
            return True
        print(".", end="", flush=True)
        time.sleep(3)
    print(" timed out.")
    return False


def _print_adb_missing():
    print("\nADB was not found on this PC.")
    print("\nQuickest fix:")
    print("  1. Download 'SDK Platform Tools for Windows' from:")
    print("     https://developer.android.com/tools/releases/platform-tools")
    print("  2. Extract the zip to  C:\\platform-tools")
    print("  3. Re-run this script — it will find ADB automatically.")
    print("     Or pass:  --adb C:\\platform-tools\\adb.exe")
    print("\nAlso make sure Developer Mode is ON in your headset:")
    print("  Meta Quest mobile app -> [your headset] -> Developer Mode -> toggle On")


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

def install_firmware(adb: str, firmware_path: Path):
    print("\n--- ADB Sideload Installation ---\n")

    devices = _adb_devices(adb)
    if not devices:
        print("No Quest headset detected over USB.")
        print("\nChecklist:")
        print("  * USB cable plugged in (use the cable that came with the Quest)")
        print("  * Developer Mode is enabled (Meta Quest app -> headset -> Developer Mode)")
        print("  * Inside the headset: accept the 'Allow USB Debugging' prompt")
        print("  * USB connection mode: File Transfer / MTP (not charging-only)")
        sys.exit(1)

    serial = devices[0]
    print(f"Headset detected: {serial}")
    size_gb = firmware_path.stat().st_size / 1024**3
    print(f"Firmware file  : {firmware_path.name}  ({size_gb:.2f} GB)")

    print("\nRebooting headset into recovery mode...")
    subprocess.run([adb, "-s", serial, "reboot", "recovery"], timeout=15)

    print(
        "\nOn the Quest headset you will see a recovery menu.\n"
        "Use the VOLUME buttons to highlight and POWER to select:\n"
        "  -> 'Apply update from ADB'\n"
        "\nThe screen will then show 'Now send the package via ADB sideload...'"
    )
    input("\nPress Enter here once the headset shows the sideload prompt... ")

    if not _wait_for_sideload(adb, timeout=60):
        print("Headset is not in sideload mode. Check the headset screen and try again.")
        sys.exit(1)

    print(f"\nTransferring firmware ({size_gb:.2f} GB)...")
    print("Do NOT disconnect the USB cable. This will take 10–20 minutes.\n")

    result = subprocess.run(
        [adb, "sideload", str(firmware_path)],
        timeout=1800,  # 30-minute ceiling
    )

    if result.returncode == 0:
        print("\nSideload finished! The headset should reboot on its own.")
        print("If it stays on the recovery screen, select 'Reboot system now'.")
    else:
        print(f"\nADB exited with code {result.returncode}.")
        print("Check the headset screen for an error message.")


# ---------------------------------------------------------------------------
# URL prompt helper
# ---------------------------------------------------------------------------

def _prompt_for_url() -> str:
    print(
        "Quest Firmware Updater\n"
        "======================\n"
        "\nHow to get the firmware URL:\n"
        "  1. Go to the Meta firmware/update page in your browser.\n"
        "  2. Right-click the download button -> 'Copy link address'\n"
        "     OR open DevTools (F12) -> Network tab, start the download,\n"
        "     find the large request, and copy its full URL.\n"
        "  3. Paste it below (or pass it as a command-line argument next time).\n"
    )
    url = input("Firmware URL: ").strip().strip('"').strip("'")
    if not url:
        sys.exit("No URL provided.")
    return url


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Download Meta Quest firmware with resume support "
            "and install it via ADB sideload."
        )
    )
    parser.add_argument("url", nargs="?", help="Firmware download URL")
    parser.add_argument(
        "--output", "-o",
        default=str(Path.home() / "Downloads" / "quest-firmware"),
        help="Folder to save the firmware (default: ~/Downloads/quest-firmware)",
    )
    parser.add_argument(
        "--adb",
        metavar="PATH",
        help="Path to adb.exe if not in PATH (auto-detected otherwise)",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download the firmware but skip installation",
    )
    parser.add_argument(
        "--install-only",
        metavar="FILE",
        help="Skip download; install this already-downloaded firmware file",
    )
    args = parser.parse_args()

    # ---- install-only mode ----
    if args.install_only:
        fw = Path(args.install_only)
        if not fw.exists():
            sys.exit(f"File not found: {fw}")
        adb = find_adb(args.adb)
        if not adb:
            _print_adb_missing()
            sys.exit(1)
        install_firmware(adb, fw)
        return

    # ---- download (+ optional install) ----
    url = args.url or _prompt_for_url()
    firmware_path = download_firmware(url, Path(args.output))

    if args.download_only:
        print(f"\nFirmware saved to: {firmware_path}")
        print("\nTo install it later:")
        print(f'  python quest_updater.py --install-only "{firmware_path}"')
        return

    adb = find_adb(args.adb)
    if not adb:
        _print_adb_missing()
        print(f"\nFirmware is already saved at: {firmware_path}")
        print("Once ADB is set up, run:")
        print(f'  python quest_updater.py --install-only "{firmware_path}"')
        sys.exit(1)

    print(f"\nADB found: {adb}")
    if input("Proceed with installation now? [Y/n] ").strip().lower() in ("", "y", "yes"):
        install_firmware(adb, firmware_path)
    else:
        print(f"\nFirmware saved at: {firmware_path}")
        print("To install later:")
        print(f'  python quest_updater.py --install-only "{firmware_path}"')


if __name__ == "__main__":
    main()
