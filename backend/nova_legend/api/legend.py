"""REST routes of the legend editor: document, grid layout, general part, export."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from rapidfuzz import fuzz, process
from starlette.background import BackgroundTask

from .. import config
from ..legend import general as general_part
from ..legend.export import build_dxf, dxf_to_dwg
from ..legend.layout import layout as place
from ..legend.general import norm_text
from ..legend.model import AP_NOTE, GRIDS, MARGIN, MAX_SHEET_WIDTH, normalize, normalize_style, propose, template_texts
from ..projects.review import build_review
from ..projects.store import Project, safe_folder_name
from ..render.engine import engine_geometry
from ..render.svg import geometry_bounds, render_svg


class LegendIn(BaseModel):
    doc: dict


class ProposeIn(BaseModel):
    style: dict | None = None


class SymbolRequest(BaseModel):
    symbol_key: str
    family_key: str | None = None
    length_mm: float | None = None
    width_mm: float | None = None


class SymbolsIn(BaseModel):
    items: list[SymbolRequest]
    strip_fill: bool = False


class DescriptionIn(BaseModel):
    family_key: str
    text: str | None = None


class CompanyLegendIn(BaseModel):
    general_path: str | None = None
    admins: list[str] | None = None
    text_size: float | None = None
    symbol_scale: float | None = None


_VIEWBOX = re.compile(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"')
ADMIN_ONLY = "Nur Admins aus den Firmeneinstellungen dürfen das ändern."


def export_name(meta: dict, part: str, ext: str) -> str:
    """edeco ag-<Bezeichnung>-<Kategorie>.dxf"""
    label = (meta.get("name") or "Projekt").strip() or "Projekt"
    part = (part or "Legende").strip() or "Legende"
    return f"{safe_folder_name('edeco ag-' + label + '-' + part)}.{ext}"


def covered_families(gen, rows: list[dict], descriptions: dict[str, str]) -> set[str]:
    """Family keys of project rows the general part already shows.

    Template project: by symbol (or family). DXF / DWG: by the text next to
    the symbol, compared with the company text and the library name of the
    row. Only an exact match of the normalised text counts; an unsure entry
    stays in the project sections.
    """
    if not gen or not gen.kind:
        return set()
    fams, syms, texts = set(gen.family_keys), set(gen.symbol_keys), set(gen.texts)
    out: set[str] = set()
    for row in rows:
        fk = row.get("family_key")
        if not fk:
            continue
        if fk in fams or (row.get("symbol_key") and row["symbol_key"] in syms):
            out.add(fk)
        elif texts and any(norm_text(t) in texts for t in (descriptions.get(fk), row.get("title")) if t):
            out.add(fk)
    return out


def register(app: FastAPI, st, project, evaluator, category_colors) -> None:
    from .app import _geometry_from_dict

    geo_cache: dict[tuple, tuple] = {}

    # -- company settings and admins ----------------------------------------------------

    def company_legend() -> dict:
        s = st.company.legend_settings()
        admins = s["legend_admins"]
        user = config.current_user()
        return {"general_path": s["legend_general_path"], "admins": admins,
                "text_size": s["legend_text_size"], "symbol_scale": s["legend_symbol_scale"],
                "user": user, "is_admin": (not admins) or user.lower() in {a.lower() for a in admins},
                "bootstrap": not admins}

    def require_admin() -> None:
        if not company_legend()["is_admin"]:
            raise HTTPException(403, ADMIN_ONLY)

    @app.get("/api/diagnostics")
    def diagnostics(project_id: str = "") -> dict:
        """Structured state for a support report. No drawing geometry."""
        datasets = []
        try:
            for d in st.library.datasets():
                datasets.append({"id": d.get("id"), "version": d.get("version"),
                                 "symbols": d.get("symbol_count"), "file": d.get("file")})
        except Exception as exc:  # noqa: BLE001 - the report should still be usable
            datasets = [{"error": str(exc)}]
        out: dict = {
            "programm": "edeco ag - NOVA Legenden",
            "version": config.APP_VERSION,
            "benutzer": config.current_user(),
            "oda_vorhanden": bool(st.settings.oda_path or config.find_oda_converter()),
            "firmenordner": st.settings.company_folder or "",
            "firmendatei": str(st.company.db_path),
            "firmenfehler": st.company_error or "",
            "datensaetze": datasets,
            "symbole": len(st.library.symbols()),
            "sync": st.sync_report,
        }
        if project_id:
            try:
                p = project(project_id)
                ev = evaluator()
                result = ev.evaluate(p)
                stored = p.legend()
                doc = normalize(stored["doc"]) if stored else None
                out["projekt"] = {
                    "id": p.id,
                    "name": p.meta().get("name"),
                    "nummer": p.meta().get("project_number"),
                    "ordner": str(p.folder),
                    "geschosse": len(result.get("plans") or []),
                    "zeilen": len(result.get("rows") or []),
                    "unbekannt": len(result.get("unknown") or []),
                    "ignoriert": len(result.get("ignored") or []),
                    "legende": bool(doc),
                    "stil": doc["style"] if doc else None,
                    "titel": doc["title"] if doc else None,
                    "abschnitte": [
                        {"titel": b["title"], "eintraege": len(b["items"]), "ebene": b.get("layer")}
                        for b in (doc["blocks"] if doc else [])
                    ],
                }
            except Exception as exc:  # noqa: BLE001
                out["projekt_fehler"] = str(exc)
        return out

    @app.get("/api/company/legend")
    def get_company_legend() -> dict:
        info = company_legend()
        info["general"] = load_general().info()
        return info

    @app.put("/api/company/legend")
    def put_company_legend(body: CompanyLegendIn) -> dict:
        require_admin()
        values: dict = {}
        if body.general_path is not None:
            values["legend_general_path"] = body.general_path.strip().strip('"')
        if body.admins is not None:
            admins = [a.strip() for a in body.admins if a.strip()]
            user = config.current_user()
            if admins and user.lower() not in {a.lower() for a in admins}:
                raise HTTPException(400, f"Trage dich selbst ({user}) in die Admin-Liste ein, sonst sperrst du dich aus.")
            values["legend_admins"] = admins
        if body.text_size is not None:
            values["legend_text_size"] = max(1.0, min(10.0, body.text_size))
        if body.symbol_scale is not None:
            values["legend_symbol_scale"] = max(0.2, min(5.0, body.symbol_scale))
        st.company.set_legend_settings(values)
        return get_company_legend()

    # -- symbol drawings -----------------------------------------------------------------

    def geometry(symbol_key: str, length_mm=None, width_mm=None):
        """(SymbolGeometry or None, engine, default length, default width), cached."""
        key = (id(st.library), symbol_key, length_mm or None, width_mm or None)
        if key in geo_cache:
            return geo_cache[key]
        detail = st.library.symbol_detail(symbol_key)
        out = (None, False, None, None)
        if detail:
            engine = bool(detail.get("engine"))
            attrs = dict(detail.get("attributes") or {})
            dl, dw = (_mm(attrs.get("L")), _mm(attrs.get("B"))) if engine else (None, None)
            if engine:
                if length_mm:
                    attrs["L"] = str(length_mm)
                if width_mm:
                    attrs["B"] = str(width_mm)
                geo = engine_geometry(detail["engine"], attrs)
            else:
                geo = _geometry_from_dict(detail["geometry"]) if detail.get("geometry") else None
            if geo is not None and not geo.primitives:
                geo = None
            out = (geo, engine, dl, dw)
        if len(geo_cache) > 5000:
            geo_cache.clear()
        geo_cache[key] = out
        return out

    def sizes_of(doc: dict) -> dict:
        out = {}
        for block in doc["blocks"]:
            for it in block["items"]:
                if it["kind"] != "symbol":
                    continue
                geo, engine, _, _ = geometry(it["symbol_key"], it["length_mm"], it["width_mm"])
                if geo is not None:
                    # drawing around its insertion point, in mm (the layout puts that point on the axis)
                    x0, y0, x1, y1 = geometry_bounds(geo)
                    out[it["id"]] = (x0 * 1000, y0 * 1000, x1 * 1000, y1 * 1000, engine)
        return out

    def load_general() -> general_part.GeneralPart:
        path = st.company.legend_settings()["legend_general_path"]
        return general_part.load(path, MAX_SHEET_WIDTH - 2 * MARGIN, st.settings.oda_path or config.find_oda_converter(),
                                 project_layout=template_layout)

    def template_layout(folder: Path):
        try:
            stored = Project(folder).legend()
        except Exception:  # noqa: BLE001 - unreadable template project
            return None
        if not stored:
            return None
        doc = normalize(stored["doc"])
        return place(doc, sizes_of(doc), include_general=False), doc["style"]["margin"], doc

    @app.post("/api/legend/symbols")
    def symbols(body: SymbolsIn) -> dict:
        """True-size SVG (viewBox in mm on paper), one answer per request in the same order."""
        fills = st.company.fill_settings()
        out = []
        for req in body.items[:500]:
            geo, engine, dl, dw = geometry(req.symbol_key, req.length_mm, req.width_mm)
            base = {"engine": engine, "length_mm": dl, "width_mm": dw}
            if geo is None:
                out.append({**base, "svg": "", "missing": st.library.symbol(req.symbol_key) is None})
                continue
            show_fill = False if body.strip_fill else fills.get(req.family_key or "", True)
            svg = render_svg(geo, None, show_points=False, show_fill=show_fill,
                             own_colors=True)
            m = _VIEWBOX.search(svg)
            out.append({**base, "svg": svg, "box": [float(v) for v in m.groups()] if m else [0, 0, 5, 5]})
        return {"items": out}

    # -- project legend -------------------------------------------------------------------

    def project_style(p) -> dict:
        s = p.settings().get("legend_style") or {}
        c = company_legend()
        return normalize_style({"text_size": s.get("text_size", c["text_size"]),
                                "symbol_scale": s.get("symbol_scale", c["symbol_scale"]),
                                "columns": s.get("columns", 2)})

    @app.get("/api/projects/{project_id}/legend")
    def get_legend(project_id: str) -> dict:
        p = project(project_id)
        stored = p.legend()
        if stored:
            stored = {**stored, "doc": normalize(stored["doc"])}
        gen = load_general()
        descriptions = st.company.descriptions()
        rows = evaluator().evaluate(p)["rows"] if gen.kind else []
        in_general = {**gen.contents(), "covered": sorted(covered_families(gen, rows, descriptions))}
        return {"legend": stored, "template_texts": template_texts(), "descriptions": descriptions,
                "in_general": in_general,
                "grids": [{"id": k, **v} for k, v in GRIDS.items()], "style": project_style(p),
                "company": company_legend(), "oda": bool(st.settings.oda_path or config.find_oda_converter())}

    @app.put("/api/projects/{project_id}/legend")
    def put_legend(project_id: str, body: LegendIn) -> dict:
        return {"legend": project(project_id).set_legend(normalize(body.doc))}

    @app.post("/api/projects/{project_id}/legend/propose")
    def propose_legend(project_id: str, body: ProposeIn | None = None) -> dict:
        """A new proposal from the current project counts. Not saved: the editor saves it."""
        p = project(project_id)
        ev = evaluator()
        result = ev.evaluate(p)
        meta = p.meta()
        title = "Legende " + " ".join(x for x in (meta.get("project_number"), meta.get("name")) if x)
        picked = category_colors(p, ev)
        colors = {c["id"]: c.get("color") for c in picked}
        layer_categories = {}
        for c in picked:
            if c.get("layer"):
                layer_categories.setdefault(c["layer"], c["id"])
        style = body.style if body and body.style else project_style(p)
        descriptions = st.company.descriptions()
        gen = load_general()
        doc = propose(result["rows"], ev.categories, bool(st.company.options().get("legend_by_category", True)),
                      descriptions, title.strip(), style=style, colors=colors,
                      covered=covered_families(gen, result["rows"], descriptions),
                      ap_covered=norm_text(AP_NOTE) in set(gen.texts),
                      layer_categories=layer_categories)
        return {"doc": doc}

    @app.post("/api/projects/{project_id}/legend/layout")
    def layout_legend(project_id: str, body: LegendIn) -> dict:
        project(project_id)
        doc = normalize(body.doc)
        gen = load_general()
        lay = place(doc, sizes_of(doc), gen.info() if gen.kind else None)
        return {**lay, "general": gen.info()}

    @app.get("/api/projects/{project_id}/legend/general")
    def general_preview(project_id: str) -> dict:
        project(project_id)
        gen = load_general()
        return {**gen.info(), "svg": gen.svg, "prims": gen.prims}

    @app.get("/api/projects/{project_id}/legend/export-name")
    def export_file_name(project_id: str, format: str = "dxf", block: str = "") -> dict:  # noqa: A002
        p = project(project_id)
        stored = p.legend()
        doc = normalize(stored["doc"]) if stored else {"blocks": []}
        target = next((b for b in doc["blocks"] if b["id"] == block), None) if block else None
        return {"name": export_name(p.meta(), target["title"] if target else "Legende",
                                    "dwg" if format.lower() == "dwg" else "dxf")}

    # The file name is part of the path, so a browser that ignores the header still saves it right.
    @app.get("/api/projects/{project_id}/legend/export/{file_name}")
    @app.get("/api/projects/{project_id}/legend/export")
    def export_legend(project_id: str, format: str = "dxf", block: str = "", general: bool = True,  # noqa: A002
                      file_name: str = ""):
        p = project(project_id)
        stored = p.legend()
        if not stored:
            raise HTTPException(400, "Für dieses Projekt gibt es noch keine Legende.")
        doc = normalize(stored["doc"])
        target_block = next((b for b in doc["blocks"] if b["id"] == block), None) if block else None
        if block and target_block is None:
            raise HTTPException(404, "Abschnitt nicht gefunden")
        gen = load_general() if general else general_part.GeneralPart()
        lay = place(doc, sizes_of(doc), gen.info() if gen.kind else None,
                    only_block=block or None, include_general=general)
        dxf = build_dxf(lay, gen if gen.kind else None,
                        lambda prim: geometry(prim["key"], prim.get("length_mm"), prim.get("width_mm"))[0],
                        doc["style"]["font"])
        ext = "dwg" if format.lower() == "dwg" else "dxf"
        name = export_name(p.meta(), target_block["title"] if target_block else "Legende", ext)
        tmp = Path(tempfile.mkdtemp(prefix="nl_legend_"))
        dxf_path = tmp / (Path(name).stem + ".dxf")
        dxf.saveas(dxf_path)
        out = dxf_path
        if ext == "dwg":
            from ..importer.dwg import ConverterMissing
            try:
                out = dxf_to_dwg(dxf_path, st.settings.oda_path or config.find_oda_converter(), tmp / "dwg")
            except ConverterMissing as exc:
                shutil.rmtree(tmp, ignore_errors=True)
                raise HTTPException(400, str(exc)) from None
            except Exception as exc:  # noqa: BLE001 - report conversion problems
                shutil.rmtree(tmp, ignore_errors=True)
                raise HTTPException(500, f"DWG konnte nicht erzeugt werden: {exc}") from None
        return FileResponse(out, filename=name, media_type="application/octet-stream",
                            background=BackgroundTask(shutil.rmtree, tmp, ignore_errors=True))

    @app.post("/api/projects/{project_id}/legend/remember")
    def remember_style(project_id: str, body: LegendIn) -> dict:
        """«Für neue Projekte merken»: text size and symbol scale become the company standard."""
        require_admin()
        project(project_id)
        style = normalize(body.doc)["style"]
        st.company.set_legend_settings({"legend_text_size": style["text_size"],
                                        "legend_symbol_scale": style["symbol_scale"]})
        return company_legend()

    # -- release check -------------------------------------------------------------------

    @app.get("/api/projects/{project_id}/review")
    def review(project_id: str) -> dict:
        """What is open before the legend is handed on (see projects/review.py)."""
        p = project(project_id)
        ev = evaluator()
        result = ev.evaluate(p)
        colors = category_colors(p, ev, result)
        stored = p.legend()
        if stored:
            stored = {**stored, "doc": normalize(stored["doc"])}
        covered = covered_families(load_general(), result["rows"], st.company.descriptions())

        def has_drawing(key: str | None) -> bool:
            sym = st.library.symbol(key) if key else None
            return bool(sym and sym.svg)

        return build_review(result, colors, stored, covered, has_drawing)

    # -- texts --------------------------------------------------------------------------

    @app.get("/api/legend/texts")
    def texts(q: str = "", family_key: str = "") -> dict:
        """Description suggestions: company text first, then the edeco legend texts by similarity."""
        company = st.company.descriptions().get(family_key) if family_key else None
        pool = template_texts()
        ranked = process.extract(q, pool, scorer=fuzz.token_set_ratio, limit=8) if q else []
        items = [{"text": t, "score": int(s), "source": "Legende edeco ag"} for t, s, _ in ranked if s >= 40]
        if company:
            items.insert(0, {"text": company, "score": 100, "source": "Firmentext"})
        return {"items": items}

    @app.put("/api/descriptions")
    def set_description(body: DescriptionIn) -> dict:
        if not body.family_key:
            raise HTTPException(400, "Familie fehlt")
        st.company.set_description(body.family_key, body.text)
        return {"ok": True, "text": st.company.descriptions().get(body.family_key)}


def _mm(value) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
