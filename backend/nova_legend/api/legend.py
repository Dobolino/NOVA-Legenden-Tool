"""REST routes of the legend editor (Phase 4)."""

from __future__ import annotations

import re

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rapidfuzz import fuzz, process

from ..legend.model import auto_layout, normalize, propose, template_texts
from ..render.engine import engine_geometry
from ..render.svg import geometry_bounds, render_svg


class LegendIn(BaseModel):
    doc: dict


class SymbolRequest(BaseModel):
    symbol_key: str
    family_key: str | None = None
    length_mm: float | None = None
    width_mm: float | None = None


class SymbolsIn(BaseModel):
    items: list[SymbolRequest]


class DescriptionIn(BaseModel):
    family_key: str
    text: str | None = None


_VIEWBOX = re.compile(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"')


def register(app: FastAPI, st, project, evaluator) -> None:
    from .app import _geometry_from_dict

    @app.get("/api/projects/{project_id}/legend")
    def get_legend(project_id: str) -> dict:
        stored = project(project_id).legend()
        return {"legend": stored, "template_texts": template_texts()}

    @app.put("/api/projects/{project_id}/legend")
    def put_legend(project_id: str, body: LegendIn) -> dict:
        return {"legend": project(project_id).set_legend(normalize(body.doc))}

    @app.post("/api/projects/{project_id}/legend/propose")
    def propose_legend(project_id: str) -> dict:
        """A new proposal from the current project counts. Not saved: the editor saves it."""
        p = project(project_id)
        ev = evaluator()
        result = ev.evaluate(p)
        meta = p.meta()
        title = "Legende " + " ".join(x for x in (meta.get("project_number"), meta.get("name")) if x)
        doc = propose(result["rows"], ev.categories, bool(st.company.options().get("legend_by_category", True)),
                      st.company.descriptions(), title.strip(), size_of=_size)
        return {"doc": doc}

    def _size(symbol_key: str) -> tuple[float, float] | None:
        """Drawing size in mm on paper (parametric luminaires at 1:50 with their default size)."""
        detail = st.library.symbol_detail(symbol_key)
        if not detail:
            return None
        if detail.get("engine"):
            geo = engine_geometry(detail["engine"], dict(detail.get("attributes") or {}))
        elif detail.get("geometry"):
            geo = _geometry_from_dict(detail["geometry"])
        else:
            return None
        if geo is None or not geo.primitives:
            return None
        x0, y0, x1, y1 = geometry_bounds(geo)
        return (x1 - x0) * 1000, (y1 - y0) * 1000

    @app.post("/api/legend/layout")
    def layout(body: LegendIn) -> dict:
        return {"doc": auto_layout(normalize(body.doc))}

    @app.post("/api/legend/symbols")
    def symbols(body: SymbolsIn) -> dict:
        """True-size SVG (viewBox in mm on paper), one answer per request in the same order."""
        fills = st.company.fill_settings()
        return {"items": [_render(req, fills) for req in body.items[:500]]}

    def _render(req: SymbolRequest, fills: dict) -> dict:
        detail = st.library.symbol_detail(req.symbol_key)
        if not detail:
            return {"svg": "", "missing": True}
        engine = bool(detail.get("engine"))
        attrs = dict(detail.get("attributes") or {})
        base = {"kind": detail.get("kind"), "engine": engine,
                "length_mm": _mm(attrs.get("L")) if engine else None,
                "width_mm": _mm(attrs.get("B")) if engine else None}
        geo = None
        if engine:
            if req.length_mm:
                attrs["L"] = str(req.length_mm)
            if req.width_mm:
                attrs["B"] = str(req.width_mm)
            geo = engine_geometry(detail["engine"], attrs)
        elif detail.get("geometry"):
            geo = _geometry_from_dict(detail["geometry"])
        if geo is None or not geo.primitives:
            return {**base, "svg": ""}
        svg = render_svg(geo, None, show_points=False, show_fill=fills.get(req.family_key or "", True))
        m = _VIEWBOX.search(svg)
        return {**base, "svg": svg, "box": [float(v) for v in m.groups()] if m else [0, 0, 5, 5]}

    @app.get("/api/legend/texts")
    def texts(q: str = "", family_key: str = "") -> dict:
        """Description suggestions: company text first, then the edeco legend texts by similarity."""
        company = st.company.descriptions().get(family_key) if family_key else None
        pool = template_texts()
        ranked = process.extract(q, pool, scorer=fuzz.token_set_ratio, limit=8) if q else []
        items = [{"text": t, "score": int(s), "source": "Legende edeco"} for t, s, _ in ranked if s >= 40]
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
