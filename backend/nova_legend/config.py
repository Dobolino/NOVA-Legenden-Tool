"""Paths and per-user settings.

Two storage places:

* local data folder (per Windows user): settings.json and the library cache
  %LOCALAPPDATA%\\NOVA-Legenden  (Linux/macOS: ~/.local/share/NOVA-Legenden)
* company folder (shared, e.g. on T:): firma.sqlite with categories and
  assignments that apply to everyone. Set in the settings page.

The environment variable NOVA_LEGENDEN_HOME overrides the local folder
(used by the tests).
"""

from __future__ import annotations

import getpass
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "NOVA-Legenden"
APP_VERSION = "0.1.0"
GITHUB_REPO = "Dobolino/NOVA-Legenden-Tool"


def build_number() -> int:
    """Build number written by the Windows build (0 = started from source)."""
    try:
        from ._build import BUILD
        return int(BUILD)
    except (ImportError, ValueError):
        return 0


# Folders searched for Nova datasets (.nzp). Depth is limited.
DATASET_SEARCH_ROOTS = [
    r"C:\Users\Public\Documents\Trimble\Warehouse",  # confirmed location at edeco
    r"T:\_CAD\NovaDat",
    r"C:\ProgramData\Trimble",
    r"C:\ProgramData\Plancal",
    r"C:\Program Files\Trimble",
    r"C:\Program Files (x86)\Trimble",
    r"C:\Users\Public\Documents\Trimble",
    r"C:\Nova",
]
DATASET_PATTERN = "Elektroinstallationen*.nzp"


def local_home() -> Path:
    env = os.environ.get("NOVA_LEGENDEN_HOME")
    if env:
        path = Path(env)
    elif sys.platform == "win32":
        path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
    else:
        path = Path.home() / ".local" / "share" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def current_user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - getuser can fail in odd environments
        return "unbekannt"


def resource_dir() -> Path:
    """Folder with bundled files (UI build). Works for source and PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    dataset_paths: list[str] = field(default_factory=list)
    company_folder: str = ""
    nova_version: str = "19.2"
    oda_path: str = ""

    @property
    def company_db(self) -> Path:
        folder = Path(self.company_folder) if self.company_folder else local_home()
        return folder / "firma.sqlite"


def settings_file() -> Path:
    return local_home() / "settings.json"


def load_settings() -> Settings:
    path = settings_file()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {k: v for k, v in data.items() if k in Settings.__dataclass_fields__}
            return Settings(**known)
        except (ValueError, TypeError):
            pass
    return Settings()


def save_settings(settings: Settings) -> None:
    path = settings_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def find_datasets(roots: list[str] | None = None, max_depth: int = 7) -> list[str]:
    """Search typical Nova folders for dataset archives."""
    found: list[str] = []
    for root in roots or DATASET_SEARCH_ROOTS:
        base = Path(root)
        if not base.is_dir():
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(base):
                depth = len(Path(dirpath).relative_to(base).parts)
                if depth >= max_depth:
                    dirnames[:] = []
                for name in filenames:
                    if Path(name).match(DATASET_PATTERN):
                        found.append(str(Path(dirpath) / name))
        except OSError:
            continue
    return sorted(set(found))


def find_oda_converter() -> str:
    """Return the path of ODAFileConverter.exe or '' if not installed."""
    candidates = []
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.extend(Path(base, "ODA").glob("ODAFileConverter*/ODAFileConverter.exe"))
    for c in sorted(candidates, reverse=True):
        if c.exists():
            return str(c)
    return ""
