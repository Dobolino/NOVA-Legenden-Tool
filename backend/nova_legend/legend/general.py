"""Locked general part (Allgemeinteil) on top of every legend.

The company sets one server file. Allowed: DXF, DWG (converted with the ODA
File Converter) or the legend of a template project (folder with
projekt.nlproj). N4D is refused: its symbol placements are not decoded, so it
cannot be shown reliably. The file is read again whenever it changed.
"""

from __future__ import annotations

import re
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
    text_x: float = 0.0                # x of the text column in drawing units (rows)
    to_mm: float = 1.0                 # drawing units -> mm
    # what the general part already shows (to leave it out of the project sections)
    texts: list[str] = field(default_factory=list)          # normalised texts (DXF / DWG)
    symbol_keys: list[str] = field(default_factory=list)    # symbols (template project)
    family_keys: list[str] = field(default_factory=list)
    # A DXF / DWG split into rows (graphic left, text right): the rows flow into the
    # columns of the legend. Empty when the drawing has no clear text column.
    rows: list[dict] = field(default_factory=list)
    symbol_area: float = 0.0           # mm from the leftmost graphic to the text column
    symbol_names: list[str] = field(default_factory=list)   # normalised names of the symbols (blocks)

    def info(self) -> dict:
        out = {"source": self.source, "kind": self.kind, "error": self.error,
               "w": round(self.w, 2), "h": round(self.h, 2), "file": self.dxf_path}
        if self.rows:
            out["rows"] = [{k: v for k, v in r.items() if k not in ("svg", "vb", "handles")} for r in self.rows]
            out["symbol_area"] = round(self.symbol_area, 3)
        return out

    def contents(self) -> dict:
        return {"texts": self.texts, "symbol_keys": self.symbol_keys, "family_keys": self.family_keys,
                "symbol_names": self.symbol_names}


def norm_text(text: str) -> str:
    """Compare texts without case, punctuation and extra spaces:
    «Leitung, nach oben» and «Leitung nach oben» are the same text."""
    t = re.sub(r"\\[A-Za-z][^;\\]*;|\\P|[{}]", " ", text or "")   # MTEXT codes
    t = re.sub(r"[^0-9a-zäöüéèàß°/]+", " ", t.lower())
    return " ".join(t.split())


_cache: dict[tuple, GeneralPart] = {}


def _files(folder: Path) -> list[Path]:
    try:
        return [f for f in folder.iterdir() if f.is_file()]
    except OSError:
        return []


def _pick_drawing(files: list[Path], prefer: str = "") -> Path | None:
    """One DXF or DWG. Prefer the folder name, then the usual Nova names
    (E_Legende, Allgemein), then a lone drawing. Several unrelated drawings
    are left for the caller to name."""
    drawings = [f for f in files if f.suffix.lower() in (".dxf", ".dwg")]
    wants = []
    for name in (prefer, "E_Legende", "Allgemein", "Legende"):
        if name and name.lower() not in wants:
            wants.append(name.lower())
    for name in wants:
        named = [f for f in drawings if f.stem.lower() == name]
        if named:
            dxf = [f for f in named if f.suffix.lower() == ".dxf"]
            return (dxf or named)[0]
    if len(drawings) == 1:
        return drawings[0]
    return None


def resolve_source(path: str) -> tuple[Path | None, str]:
    """The file to read for a typed path.

    A folder may hold the drawing (``Allgemein.dxf`` inside ``Allgemein``) or a template
    project (``projekt.nlproj``). A path without an extension also matches ``.dxf`` / ``.dwg``.
    """
    raw = (path or "").strip().strip('"')
    if not raw:
        return None, ""
    p = Path(raw)
    if p.is_dir():
        project = p / "projekt.nlproj"
        if project.is_file():
            return project, ""
        found = _files(p)
        drawing = _pick_drawing(found, p.name)
        if drawing:
            return drawing, ""
        n4d = [f.name for f in found if f.suffix.lower() == ".n4d"]
        if n4d:
            return None, f"{NOT_SUPPORTED} Im Ordner liegt {', '.join(n4d)}."
        names = ", ".join(sorted(f.name for f in found)[:8])
        extra = f" Im Ordner liegen: {names}." if names else " Der Ordner enthält keine Datei."
        return None, ("Im Ordner liegt keine DXF- oder DWG-Datei und kein Vorlagen-Projekt "
                      f"(projekt.nlproj).{extra}")
    if p.is_file():
        return p, ""
    if p.suffix == "":
        for ext in (".dxf", ".dwg"):
            cand = Path(str(p) + ext)
            if cand.is_file():
                return cand, ""
    if p.parent.is_dir():
        drawing = _pick_drawing(_files(p.parent), p.name)
        if drawing:
            return drawing, ""
    return None, f"Servervorlage nicht gefunden: {raw}"


def load(path: str, inner_width: float, oda_exe: str | None, project_layout=None) -> GeneralPart:
    """Read the general part. ``project_layout(folder)`` returns a layout of a project legend."""
    path = (path or "").strip().strip('"')
    if not path:
        return GeneralPart()
    target, missing = resolve_source(path)
    if target is None:
        return GeneralPart(source=path, error=missing)
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
    lay, margin, doc = result
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
    items = [it for b in doc["blocks"] for it in b["items"] if not it.get("hidden")]
    return GeneralPart(source=source, kind="project", w=lay["width"] - 2 * margin,
                       h=lay["height"] - 2 * margin, prims=prims,
                       symbol_keys=sorted({it["symbol_key"] for it in items if it.get("symbol_key")}),
                       family_keys=sorted({it["family_key"] for it in items if it.get("family_key")}),
                       texts=sorted({norm_text(it["text"]) for it in items if it["kind"] == "note"}))


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
    part.to_mm = to_mm
    part.svg = _svg(doc, part.w, part.h)
    part.texts = _texts(msp)
    try:
        rows, area, text_x = split_rows(doc, to_mm)
    except Exception:  # noqa: BLE001 - without rows the drawing is placed as a whole
        rows, area, text_x = [], 0.0, 0.0
    if len(rows) >= 3:
        part.rows, part.symbol_area, part.text_x = rows, area, text_x
        part.symbol_names = sorted({n for r in rows for n in r.get("names", [])})
    return part


def _mark_focus(ents, to_mm: float, x0: float, y0: float, x1: float, y1: float) -> list[float]:
    """Where the bulky part sits inside the row graphic, as fractions of the box.

    A long stroke next to a small symbol must not pull the symbol into a corner:
    the symbol (circle, insert, closed shape) is the part we centre in the tile."""
    from ezdxf import bbox

    cx = cy = weight = 0.0
    pieces = []
    for e, box in ents:
        if e.dxftype() == "INSERT":
            try:
                for ve in e.virtual_entities():
                    b = bbox.extents([ve], fast=True)
                    if b.has_data:
                        pieces.append(b)
                continue
            except Exception:  # noqa: BLE001 - the insert itself still counts
                pass
        if box.has_data:
            pieces.append(box)
    for b in pieces:
        ww = (b.extmax.x - b.extmin.x) * to_mm
        hh = (b.extmax.y - b.extmin.y) * to_mm
        if hh <= 0.35 and ww > hh * 4:
            continue
        area = max(ww * hh, 0.05)
        cx += (b.extmin.x + b.extmax.x) / 2 * area
        cy += (b.extmin.y + b.extmax.y) / 2 * area
        weight += area
    if weight <= 0 or x1 <= x0 or y1 <= y0:
        return [0.5, 0.5]
    return [round(min(1.0, max(0.0, (cx / weight - x0) / (x1 - x0))), 4),
            round(min(1.0, max(0.0, (cy / weight - y0) / (y1 - y0))), 4)]


def _is_line_graphic(row: dict) -> bool:
    """A flat stroke (a cable, a colour bar). It stays one readable sample, not a scaled symbol."""
    gw, gh = float(row.get("gw") or 0.0), float(row.get("gh") or 0.0)
    if gw <= 0:
        return False
    return gh <= 0.35


def _row_factor(value, lo: float, hi: float) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 1.0
    if n != n:  # NaN
        return 1.0
    return max(lo, min(hi, n))


def apply_overrides(part: GeneralPart, overrides: dict) -> GeneralPart:
    """The general part with the company's row changes: another text, a hidden row,
    symbol families the row stands for. Returns a copy; the cached part stays as read."""
    from dataclasses import replace

    if not part.rows:
        return part
    rows = []
    families = set(part.family_keys)
    hidden_texts: set[str] = set()
    for r in part.rows:
        key = norm_text(r["text"])
        o = overrides.get(key) or {}
        if o.get("hidden"):
            # a hidden row is gone: its text and symbol must not stay out of the project sections
            hidden_texts.add(key)
            continue
        families.update(o.get("links") or [])
        place = str(o.get("text_place") or "bottom")
        if place not in ("top", "middle", "bottom"):
            place = "bottom"
        try:
            rotation = int(o.get("rotation") or 0) % 360
        except (TypeError, ValueError):
            rotation = 0
        rows.append({**r, "key": key, "text": (o.get("text") or "").strip() or r["text"],
                     "text_scale": _row_factor(o.get("text_scale"), 0.5, 3.0),
                     "symbol_factor": _row_factor(o.get("symbol_factor"), 0.3, 4.0),
                     "rotation": rotation, "text_place": place, "line": _is_line_graphic(r)})
    texts = (set(part.texts) - hidden_texts) | {norm_text(r["text"]) for r in rows}
    names = sorted({n for r in rows for n in (r.get("names") or [])})
    return replace(part, rows=rows, family_keys=sorted(families), texts=sorted(texts), symbol_names=names)


# -- rows of a DXF general part -----------------------------------------------------------

_SUFFIX = re.compile(r"_[A-Z0-9]{8,12}$")       # Nova appends an id to every block name


def block_title(name: str) -> str:
    """«Steigleitung_ nach oben_A09TKTBGG3» -> «Steigleitung, nach oben» (the Nova name)."""
    return _SUFFIX.sub("", name).replace("_ ", ", ").replace("_", " ").strip()


def split_rows(doc, to_mm: float) -> tuple[list[dict], float, float]:
    """Split a legend drawing into rows: every text in the text column with the graphic
    left of it at the same height; a text outside the column without graphic is a heading.
    Returns (rows top down, width of the symbol area in mm, x of the text column in
    drawing units). Positions stay in drawing units, sizes are in mm."""
    from collections import Counter

    from ezdxf import bbox

    msp = doc.modelspace()
    texts = []
    for e in msp.query("TEXT MTEXT"):
        if e.dxftype() == "TEXT":
            raw, height = e.dxf.text, float(e.dxf.height)
        else:
            raw, height = e.plain_text(), float(e.dxf.char_height)
        raw = " ".join(str(raw).split())
        if raw:
            texts.append((e, raw, height))
    big = [t for t in texts if t[2] * to_mm >= 1.5 and len(t[1]) > 1]
    if not big:
        return [], 0.0, 0.0
    text_x = Counter(round(t[0].dxf.insert.x, 1) for t in big).most_common(1)[0][0]
    rows: list[dict] = []
    # a few millimetres of jitter still count as the same text column
    tol = max(3.0 / max(to_mm, 1e-6), 1.5)
    in_column = [t for t in big if abs(t[0].dxf.insert.x - text_x) < tol]
    for e, raw, height in in_column:
        rows.append({"text": raw, "heading": False, "y": e.dxf.insert.y + height * 0.36,
                     "text_h": round(height * to_mm, 3), "ents": [], "names": []})
    taken = {id(t[0]) for t in in_column}
    for e, raw, height in big:
        if id(e) in taken:
            continue
        y = e.dxf.insert.y + height * 0.36
        if all(abs(r["y"] - y) > height for r in rows) and len(raw) > 2:
            rows.append({"text": raw, "heading": True, "y": y, "text_h": round(height * to_mm, 3),
                         "ents": [], "names": []})
            taken.add(id(e))
    rows.sort(key=lambda r: -r["y"])
    if len(rows) < 3:
        return [], 0.0, 0.0
    pitch = sorted(abs(a["y"] - b["y"]) for a, b in zip(rows, rows[1:]))[len(rows) // 2] or 1.0
    for e in msp:
        if id(e) in taken or e.dxftype() in ("POINT", "VIEWPORT"):
            continue
        box = bbox.extents([e], fast=True)
        if not box.has_data:
            continue
        cx, cy = (box.extmin.x + box.extmax.x) / 2, (box.extmin.y + box.extmax.y) / 2
        if cx > text_x - 0.3:
            continue                     # right of the text column: not part of a symbol
        row = min(rows, key=lambda r: abs(r["y"] - cy))
        if abs(row["y"] - cy) > pitch * 0.8:
            continue
        row["ents"].append((e, box))
        if e.dxftype() == "INSERT":
            row["names"].append(norm_text(block_title(e.dxf.name)))
    left = min((b.extmin.x for r in rows for _e, b in r["ents"]), default=text_x)
    area = (text_x - left) * to_mm
    out = []
    for i, r in enumerate(rows):
        item = {"id": f"g{i}", "text": r["text"], "heading": r["heading"], "text_h": r["text_h"],
                "names": sorted(set(r["names"]))}
        if r["ents"]:
            # patterned lines (dashed, dash-dot ...) keep a readable rhythm at 1:1 on paper
            from .linetypes import simplify_linetypes, tune_entities
            if not getattr(doc, "_nl_simple_lt", False):
                simplify_linetypes(doc)
                doc._nl_simple_lt = True
            tune_entities(doc, [e for e, _b in r["ents"]], to_mm)
            x0 = min(b.extmin.x for _e, b in r["ents"])
            y0 = min(b.extmin.y for _e, b in r["ents"])
            x1 = max(b.extmax.x for _e, b in r["ents"])
            y1 = max(b.extmax.y for _e, b in r["ents"])
            item.update({"gx": round((x0 - text_x) * to_mm, 3), "gw": round((x1 - x0) * to_mm, 3),
                         "gh": round((y1 - y0) * to_mm, 3),
                         "focus": _mark_focus(r["ents"], to_mm, x0, y0, x1, y1),
                         "src": [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)],
                         "handles": [e.dxf.handle for e, _b in r["ents"]]})
            item["vb"], item["svg"] = _row_svg(doc, [e for e, _b in r["ents"]], (x0, y0, x1, y1), f"g{i}")
        out.append(item)
    return out, area, text_x


def _row_svg(doc, entities, box, prefix: str = "g") -> tuple[str, str]:
    """(viewBox, inner SVG) of the graphic of one row, original colours, no paper.
    The style classes get the row prefix: all rows share one page in the editor."""
    try:
        from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, svg
        from ezdxf.math import BoundingBox2d

        backend = svg.SVGBackend()
        cfg = config.Configuration(background_policy=config.BackgroundPolicy.OFF,
                                   color_policy=config.ColorPolicy.COLOR)
        Frontend(RenderContext(doc), backend, config=cfg).draw_entities(entities)
        x0, y0, x1, y1 = box
        pad = max(x1 - x0, y1 - y0) * 0.02 + 1e-6
        page = layout.Page(max(x1 - x0, 0.1), max(y1 - y0, 0.1), layout.Units.mm, margins=layout.Margins.all(0))
        text = backend.get_string(page, render_box=BoundingBox2d([(x0 - pad, y0 - pad), (x1 + pad, y1 + pad)]),
                                  settings=layout.Settings(fit_page=True), xml_declaration=False)
        m = re.search(r'viewBox="([^"]+)"', text)
        inner = text[text.find(">", text.find("<svg")) + 1:text.rfind("</svg>")]
        inner = re.sub(r'<rect fill="[^"]*" x="0" y="0"[^>]*/>', "", inner, count=1)   # the paper
        inner = re.sub(r'\.C([0-9A-F]+) ', lambda m: f".{prefix}C{m.group(1)} ", inner)
        inner = re.sub(r'class="C([0-9A-F]+)"', lambda m: f'class="{prefix}C{m.group(1)}"', inner)
        return (m.group(1) if m else "0 0 1 1"), inner
    except Exception:  # noqa: BLE001 - the export still has the graphic
        return "0 0 1 1", ""


def _texts(msp) -> list[str]:
    """All texts of the drawing, also those inside blocks, normalised."""
    from ezdxf import disassemble

    out: set[str] = set()
    try:
        for e in disassemble.recursive_decompose(msp):
            kind = e.dxftype()
            if kind == "TEXT" or kind == "ATTRIB":
                raw = e.dxf.text
            elif kind == "MTEXT":
                raw = e.plain_text()
            else:
                continue
            for part in str(raw).splitlines():
                t = norm_text(part)
                if len(t) >= 3:
                    out.add(t)
    except Exception:  # noqa: BLE001 - no texts means nothing is left out
        return sorted(out)
    return sorted(out)


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
