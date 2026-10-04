"""Program update from GitHub releases.

Every Windows build is published as a release with the tag
``v<version>-build.<number>`` and the asset ``NOVA-Legenden-Setup-<version>.exe``.
The update:

1. asks the GitHub API for the newest release of the chosen channel:
   "stable" takes the latest normal release (builds of main), "test" also
   takes pre-releases (builds of development branches),
2. compares version and build number with the running program,
3. downloads the setup into the temp folder and checks size and SHA-256,
4. starts the setup silently (no admin rights needed) and closes the program.
   The setup restarts NOVA-Legenden when it is done.

Needs internet access to api.github.com and github.com.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from . import config

log = logging.getLogger(__name__)
TAG_RE = re.compile(r"^v(\d+(?:\.\d+)*)(?:-build\.(\d+))?$")
API_URL = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest"   # never a pre-release
LIST_URL = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases?per_page=30"
CHANNELS = ("stable", "test")


@dataclass
class UpdateInfo:
    current: str
    latest: str
    available: bool
    can_install: bool
    notes: str = ""
    published: str = ""
    asset_url: str = ""
    asset_name: str = ""
    size: int = 0
    sha256: str = ""
    page_url: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def parse_tag(tag: str) -> tuple[tuple[int, ...], int] | None:
    m = TAG_RE.match(tag.strip())
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split(".")), int(m.group(2) or 0)


def current_label() -> str:
    build = config.build_number()
    return f"{config.APP_VERSION} (Build {build})" if build else f"{config.APP_VERSION} (Quellcode)"


def is_installed() -> bool:
    """True for the frozen Windows program (only then the setup can replace it)."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def _get_json(url: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"NOVA-Legenden/{config.APP_VERSION}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def _newest(releases: list[dict]) -> dict:
    """Newest release by version and build number, pre-releases included, drafts not."""
    ranked = [(parse_tag(r.get("tag_name", "")), r) for r in releases if not r.get("draft")]
    ranked = [(t, r) for t, r in ranked if t]
    if not ranked:
        return {}
    return max(ranked, key=lambda tr: tr[0])[1]


def check(fetch=_get_json, channel: str = "stable") -> UpdateInfo:
    """Ask GitHub for the newest release of the channel. Never raises: errors go into .message."""
    info = UpdateInfo(current_label(), "", False, is_installed())
    try:
        data = _newest(fetch(LIST_URL)) if channel == "test" else fetch(API_URL)
    except Exception as exc:  # noqa: BLE001 - network problems are reported to the user
        info.message = f"Keine Verbindung zu GitHub: {exc}"
        return info
    tag = data.get("tag_name", "")
    parsed = parse_tag(tag)
    if not parsed:
        info.message = f"Unbekanntes Release-Format: {tag}"
        return info
    version, build = parsed
    info.latest = f"{'.'.join(map(str, version))} (Build {build})"
    info.notes = data.get("body") or ""
    info.published = data.get("published_at") or ""
    info.page_url = data.get("html_url") or ""
    asset = next((a for a in data.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None)
    if asset:
        info.asset_url = asset.get("browser_download_url", "")
        info.asset_name = asset.get("name", "")
        info.size = int(asset.get("size") or 0)
        digest = asset.get("digest") or ""
        info.sha256 = digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
    own_version = tuple(int(p) for p in config.APP_VERSION.split("."))
    own_build = config.build_number()
    info.available = bool(asset) and (version, build) > (own_version, own_build)
    if not asset:
        info.message = "Das neueste Release enthält kein Setup."
    elif not info.available:
        info.message = "Du hast die neueste Version."
    elif not info.can_install:
        info.message = "Update nur in der installierten Windows-Version möglich."
    return info


def download(info: UpdateInfo, target_dir: Path | None = None, opener=urllib.request.urlopen) -> Path:
    """Download the setup and verify size and checksum."""
    folder = target_dir or Path(tempfile.gettempdir()) / "NOVA-Legenden-Update"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (info.asset_name or "NOVA-Legenden-Setup.exe")
    req = urllib.request.Request(info.asset_url, headers={"User-Agent": "NOVA-Legenden"})
    digest = hashlib.sha256()
    size = 0
    tmp = target.with_suffix(".part")
    with opener(req, timeout=60) as res, open(tmp, "wb") as fh:
        while True:
            chunk = res.read(1 << 16)
            if not chunk:
                break
            fh.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    if info.size and size != info.size:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"Download unvollständig ({size} von {info.size} Byte)")
    if info.sha256 and digest.hexdigest() != info.sha256:
        tmp.unlink(missing_ok=True)
        raise ValueError("Prüfsumme des Downloads stimmt nicht")
    tmp.replace(target)
    return target


_pending: list[str] | None = None
_pending_lock = threading.Lock()


def launch_pending() -> bool:
    """Start the setup that ``install`` prepared. Called once the window is closed,
    so the setup never closes a running window (that crashed .NET)."""
    global _pending
    with _pending_lock:
        args, _pending = _pending, None
    if not args:
        return False
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    log.info("Starte Update: %s", " ".join(args))
    subprocess.Popen(args, creationflags=flags, close_fds=True)  # noqa: S603 - our own verified setup
    return True


def install(setup: Path, shutdown, fallback_after: float = 15.0) -> None:
    """Close this program, then start the setup silently.

    The window closes first (``shutdown``); the main thread then calls
    ``launch_pending`` when the window loop has ended. If the window does not
    close within ``fallback_after`` seconds the setup starts anyway and the
    process ends.
    """
    global _pending
    with _pending_lock:
        _pending = [str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"]

    def later() -> None:
        time.sleep(0.8)                 # the HTTP answer reaches the page first
        try:
            shutdown()
        except Exception:  # noqa: BLE001 - the fallback below still installs
            log.warning("Fenster liess sich nicht schliessen", exc_info=True)
        time.sleep(fallback_after)
        if launch_pending():
            os._exit(0)

    threading.Thread(target=later, daemon=True).start()
