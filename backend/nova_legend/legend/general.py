"""Locked general part (Allgemeinteil) on top of every legend.

The company sets one server file. Allowed: DXF, DWG (converted with the ODA
File Converter) or the legend of a template project (folder with
projekt.nlproj). N4D is refused: its symbol placements are not decoded, so it
cannot be shown reliably. The file is read again whenever it changed.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

NOT_SUPPORTED = ("Die Servervorlage für den Allgemeinteil muss eine DXF- oder DWG-Datei oder ein "
                 "Vorlagen-Projekt mit Legende sein. N4D lässt sich nicht sicher lesen.")
UNITS_TO_MM = {1: 25.4, 4: 1.0, 5: 10.0, 6: 1000.0}


@dataclass
class GeneralPart:
    source: str = ""
    kind: str = ""                     # "dxf", "project" or "" (none / error)
    error: str = ""
    w: float = 0.0                     # fitted size in mm on the sheet
    h: float = 0.0
    svg: str = ""                      # preview for a DXF source
    prims: list[dict] = field(default_factory=list)   # placed primitives for a project source
    dxf_path: str = ""                 # DXF to copy into the export
    scale: float = 1.0                 # drawing units -> sheet mm
    ext_min: tuple[float, float] = (0.0, 0.0)
    ext_max: tuple[float, float] = (0.0, 0.0)

    def info(self) -> dict:
        return {"source": self.source, "kind": self.kind, "error": self.error,
                "w": round(self.w, 2), "h": round(self.h, 2)}


_cache: dict[tuple, GeneralPart] = {}


def load(path: str, inner_width: float, oda_exe: str | None, project_layout=None) -> GeneralPart:
    """Read the general part. ``project_layout(folder)`` returns a layout of a project legend."""
    path = (path or "").strip().strip('"')
    if not path:
        return GeneralPart()
    p = Path(path)
    target = p / "projekt.nlproj" if p.is_dir() else p
    try:
        mtime = target.stat().st_mtime
    except OSError:
        return GeneralPart(source=path, error=f"Servervorlage nicht gefunden: {path}")
    key = (str(target), mtime, round(inner_width, 2), bool(oda_exe))
    if key in _cache and target.suffix.lower() in (".dxf", ".dwg"):
        return _cache[key]
    suffix = target.suffix.lower()
    if suffix == ".nlproj":
        part = _from_project(path, target.parent, project_layout)
    elif suffix == ".dxf":
        part = _from_dxf(path, target, inner_width)
    elif suffix == ".dwg":
        part = _from_dwg(path, target, inner_width, oda_exe)
    else:
        part = GeneralPart(source=path, error=NOT_SUPPORTED)
    if part.kind in ("dxf",):
        _cache[key] = part
    return part


def _from_project(source: str, folder: Path, project_layout) -> GeneralPart:
    if project_layout is None:
        return GeneralPart(source=source, error=NOT_SUPPORTED)
    result = project_layout(folder)
    if result is None:
        return GeneralPart(source=source, error="Das Vorlagen-Projekt hat noch keine Legende.")
    lay, margin = result
    prims = []
    for prim in lay["prims"]:
        q = dict(prim)
        for k in ("x", "cx", "x1", "x2"):
            if k in q:
                q[k] = round(q[k] - margin, 3)
        for k in ("y", "cy", "y1", "y2"):
            if k in q:
                q[k] = round(q[k] - margin, 3)
        if q["t"] != "hit":
            prims.append(q)
    return GeneralPart(source=source, kind="project", w=lay["width"] - 2 * margin,
                       h=lay["height"] - 2 * margin, prims=prims)


def _from_dwg(source: str, dwg: Path, inner_width: float, oda_exe: str | None) -> GeneralPart:
    from ..importer.dwg import ConverterMissing, convert_dwg_to_dxf

    out_dir = Path(tempfile.mkdtemp(prefix="nl_general_"))
    try:
        dxf = convert_dwg_to_dxf(dwg, oda_exe or "", out_dir)
        keep = Path(tempfile.mkdtemp(prefix="nl_general_dxf_")) / dxf.name
        shutil.copy2(dxf, keep)
        part = _from_dxf(source, keep, inner_width)
        return part
    except ConverterMissing as exc:
        return GeneralPart(source=source, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - any conversion problem is shown
        return GeneralPart(source=source, error=f"DWG konnte nicht gelesen werden: {exc}")
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def _from_dxf(source: str, path: Path, inner_width: float) -> GeneralPart:
    import ezdxf
    from ezdxf import bbox

    try:
        doc = ezdxf.readfile(str(path))
    except Exception as exc:  # noqa: BLE001 - unreadable file
        return GeneralPart(source=source, error=f"DXF konnte nicht gelesen werden: {exc}")
    msp = doc.modelspace()
    ext = bbox.extents(msp, fast=True)
    if not ext.has_data:
        return GeneralPart(source=source, error="Die Servervorlage ist leer.")
    (x0, y0, _), (x1, y1, _) = ext.extmin, ext.extmax
    units = int(doc.header.get("$INSUNITS", 0) or 0)
    to_mm = UNITS_TO_MM.get(units) or (1000.0 if max(x1 - x0, y1 - y0) < 5 else 1.0)
    w_mm, h_mm = (x1 - x0) * to_mm, (y1 - y0) * to_mm
    fit = min(1.0, inner_width / w_mm) if w_mm > 0 else 1.0
    part = GeneralPart(source=source, kind="dxf", w=w_mm * fit, h=h_mm * fit, dxf_path=str(path),
                       scale=to_mm * fit, ext_min=(x0, y0), ext_max=(x1, y1))
    part.svg = _svg(doc, part.w, part.h)
    return part


def _svg(doc, w: float, h: float) -> str:
    """Preview of the DXF with ezdxf's drawing add-on (white background, original colours)."""
    try:
        from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, svg

        backend = svg.SVGBackend()
        cfg = config.Configuration(background_policy=config.BackgroundPolicy.WHITE,
                                   color_policy=config.ColorPolicy.COLOR)
        Frontend(RenderContext(doc), backend, config=cfg).draw_layout(doc.modelspace())
        page = layout.Page(w, h, layout.Units.mm, margins=layout.Margins.all(0))
        text = backend.get_string(page, settings=layout.Settings(fit_page=True))
        return text[text.find("<svg"):] if "<svg" in text else ""
    except Exception:  # noqa: BLE001 - the export still works without a preview
        return ""
