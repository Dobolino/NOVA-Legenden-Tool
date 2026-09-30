"""Paths and per-user settings.

Two storage places:

* local data folder (per Windows user): settings.json and the library cache
  %LOCALAPPDATA%\\NOVA-Legenden  (Linux/macOS: ~/.local/share/NOVA-Legenden)
* company folder (shared, e.g. on T:): edeco ag-Legenden-firma.sqlite with
  categories and assignments that apply to everyone. Set in the settings page.

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


# Folder searched for Nova datasets (.nzp). At edeco all datasets that are
# used live here; other folders (e.g. installer copies on T:) are not searched.
DATASET_SEARCH_ROOTS = [
    r"C:\Users\Public\Documents\Trimble\Warehouse",
]
DATASET_PATTERN = "*.nzp"


def dataset_summary(path: Path) -> tuple[str, int] | None:
    """(dataset id, number of symbols) for a Nova electrical dataset, else None.

    Electrical = DataFormat 'nova…_elo'. The Warehouse folder also holds HVAC and
    sanitary datasets; they are skipped.
    """
    import zipfile

    from .parser import tree

    try:
        with zipfile.ZipFile(path) as zf:
            attrs = tree.parse(zf.read("Set")).root.attrs
            if not attrs.get("DataFormat", "").endswith("_elo"):
                return None
            graphic = tree.parse(zf.read("Graphic")).root if "Graphic" in zf.namelist() else None
    except Exception:  # noqa: BLE001 - unreadable files are simply skipped
        return None
    count = sum(1 for g in graphic.find_all("GraphicItem") if g.get("Item")) if graphic else 0
    return attrs.get("ID", path.stem), count


def is_electrical_dataset(path: Path) -> bool:
    return dataset_summary(path) is not None


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


DEFAULT_PROJECTS_FOLDER = r"T:\_CAD\NovaDat\NovaFirma12\Makro\Legenden"
COMPANY_DB_NAME = "edeco ag-Legenden-firma.sqlite"
LEGACY_COMPANY_DB_NAME = "firma.sqlite"


def resolve_company_db(folder: Path) -> Path:
    """Path of the shared company file.

    Older installs used firma.sqlite. If that file is still there and the new
    name is not, it is renamed once and then reused.
    """
    folder = Path(folder)
    current = folder / COMPANY_DB_NAME
    legacy = folder / LEGACY_COMPANY_DB_NAME
    if legacy.is_file() and not current.exists():
        try:
            legacy.rename(current)
        except OSError:
            return legacy
    return current


@dataclass
class Settings:
    dataset_paths: list[str] = field(default_factory=list)
    company_folder: str = ""
    projects_folder: str = DEFAULT_PROJECTS_FOLDER
    nova_version: str = "19.2"
    oda_path: str = ""
    ui_theme: str = "system"          # "system", "light" or "dark" (this computer)

    @property
    def company_db(self) -> Path:
        folder = Path(self.company_folder) if self.company_folder else local_home()
        return resolve_company_db(folder)


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


def find_datasets(roots: list[str] | None = None, max_depth: int = 7,
                  skip_ids: set[str] | None = None) -> list[str]:
    """Search the Nova folder for electrical datasets.

    Skips empty catalogues (no symbols), datasets whose id is in ``skip_ids``
    and further copies of a dataset that was already found.
    """
    found: list[str] = []
    seen: set[str] = set(skip_ids or ())
    for root in roots or DATASET_SEARCH_ROOTS:
        base = Path(root)
        if not base.is_dir():
            continue
        try:
            walk = sorted(os.walk(base), key=lambda w: w[0])
        except OSError:
            continue
        for dirpath, dirnames, filenames in walk:
            if len(Path(dirpath).relative_to(base).parts) >= max_depth:
                continue
            for name in sorted(filenames):
                path = Path(dirpath) / name
                if not path.match(DATASET_PATTERN):
                    continue
                summary = dataset_summary(path)
                if not summary or summary[1] == 0 or summary[0] in seen:
                    continue
                seen.add(summary[0])
                found.append(str(path))
    return found


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
