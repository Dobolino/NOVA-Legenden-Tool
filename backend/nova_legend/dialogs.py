"""Native file and folder dialogs of the program window (pywebview).

The window registers itself with ``attach``. In browser or server mode there
is no window: ``available()`` is False and the UI keeps the text fields.
Cancel returns None, so the caller keeps the previous value.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

KINDS = {
    "dataset": {"folder": False, "types": ("Nova-Datensatz (*.nzp)", "Alle Dateien (*.*)")},
    "folder": {"folder": True, "types": ()},
}

_window = None


def attach(window) -> None:
    global _window
    _window = window


def available() -> bool:
    return _window is not None


def _dialog_type(folder: bool):
    import webview  # only present in the Windows build

    enum = getattr(webview, "FileDialog", None)
    if enum is not None:
        return enum.FOLDER if folder else enum.OPEN
    return webview.FOLDER_DIALOG if folder else webview.OPEN_DIALOG


def choose(kind: str, start: str = "") -> str | None:
    """Show the dialog and return the chosen path, or None on cancel."""
    if kind not in KINDS:
        raise ValueError(f"unbekannter Dialog: {kind}")
    if _window is None:
        raise RuntimeError("Dateidialoge gibt es nur im Programmfenster")
    spec = KINDS[kind]
    directory = ""
    if start:
        p = Path(start)
        directory = str(p if p.is_dir() else p.parent) if (p.is_dir() or p.parent.is_dir()) else ""
    result = _window.create_file_dialog(_dialog_type(spec["folder"]), directory=directory,
                                        allow_multiple=False, file_types=spec["types"])
    if not result:
        return None
    path = result[0] if isinstance(result, (list, tuple)) else result
    return str(path) or None
