"""Simplified previews of parametric Nova symbols (no Trimble files needed)."""

from nova_legend.render.engine import engine_geometry, is_engine_preview
from nova_legend.render.svg import geometry_bounds, render_svg


def test_rectangle_luminaire_uses_part_size():
    geo = engine_geometry("2DNeutral;Typ=0;A=*L;B=*;A1=0;B1=0", {"L": "1200", "B": "300"})
    x0, y0, x1, y1 = geometry_bounds(geo)
    assert round((x1 - x0) / (y1 - y0), 3) == 4.0          # 1200 x 300 keeps its ratio
    assert is_engine_preview(geo)


def test_frame_fill_and_lines():
    geo = engine_geometry("2DNeutral;Typ=0;A=*L;B=*;A1=0,05;B1=0,05;Fill=1|4|5|8;Lines=3",
                          {"L": "600", "B": "600"})
    kinds = [(p.kind, p.filled) for p in geo.primitives]
    assert kinds.count(("polygon", True)) == 4             # four filled sectors
    assert kinds.count(("line", False)) == 3               # three inner lines
    assert kinds.count(("polygon", False)) == 2            # outline + frame


def test_round_luminaire_and_distribution_box():
    round_geo = engine_geometry("2DNeutral;Typ=1;A=*L;B=*", {"L": "600", "B": "600"})
    assert round_geo.primitives[-1].kind == "ellipse_arc"
    box = engine_geometry("Verteiler;H=*H;B=*L;T=*B;AP=1;Darstellung=3", {"L": "800", "B": "250"})
    assert [p.filled for p in box.primitives].count(True) == 1   # diagonal filled
    assert "<path" in render_svg(box, None)


def test_unknown_engine_gives_no_preview():
    assert engine_geometry("Unbekannt;X=1", {}) is None
    assert engine_geometry(None, {}) is None
