"""Phase 4: legend document on a fixed grid, general part, admins and DXF export."""

from __future__ import annotations

import ezdxf
import pytest

from nova_legend import config
from nova_legend.legend.layout import layout, text_width, wrap
from nova_legend.legend.model import AP_NOTE, empty_doc, normalize, propose, section_style
from nova_legend.render.engine import engine_geometry
from nova_legend.render.svg import geometry_bounds

from test_phase2 import import_dxf, nova_like_dxf
from test_phase3 import env  # noqa: F401 - fixture

CATS = [{"id": "allgemein", "title": "Allgemein", "layer": "E_Starkstrom"},
        {"id": "schalter", "title": "Schalter und Taster", "layer": "E_Licht"},
        {"id": "versteckt", "title": "Versteckt", "hidden": True}]


def row(key, cats, total=2, mountings=None):
    return {"family_key": key, "symbol_key": f"sym:{key}", "title": key.title(), "categories": cats,
            "total": total, "mountings": mountings or {"UP": total}}


def block(title, n, text="Eintrag", kind="note"):
    return {"id": title, "title": title, "items": [{"id": f"{title}{k}", "kind": kind, "text": text}
                                                   for k in range(n)]}


def boxes(lay, kind="item"):
    return [p for p in lay["prims"] if p["t"] == "hit" and p["kind"] == kind]


def overlap(a, b):
    return a["x"] < b["x"] + b["w"] - 1e-6 and b["x"] < a["x"] + a["w"] - 1e-6 and \
        a["y"] < b["y"] + b["h"] - 1e-6 and b["y"] < a["y"] + a["h"] - 1e-6


# -- proposal ----------------------------------------------------------------------

def test_proposal_groups_by_first_visible_category_with_section_colours():
    rows = [row("schalter", ["schalter"]), row("dose", ["allgemein", "schalter"]),
            row("weg", ["schalter"], total=0), row("geheim", ["versteckt"]), row("frei", [])]
    doc = propose(rows, CATS, True, {"dose": "UP-Abzweigdose Decke / Wand"}, "Legende 1424",
                  style={"columns": 3, "text_size": 3}, colors={"schalter": "#0000ff"})
    assert [b["title"] for b in doc["blocks"]] == ["Allgemein", "Schalter und Taster", "Ohne Kategorie"]
    assert [i["text"] for i in doc["blocks"][0]["items"]] == ["UP-Abzweigdose Decke / Wand"]
    sch = doc["blocks"][1]
    assert sch["style"]["header"] == "#0000ff" and sch["style"]["symbol"] == "#0000ff"   # layer colour
    assert sch["style"]["background_on"] is False and sch["style"]["border_on"] is False
    assert sch["style"]["header_text"] == "#ffffff" and sch["layer"] == "E_Licht"
    assert doc["style"]["columns"] == 3 and doc["style"]["text_size"] == 3
    keys = {i["family_key"] for b in doc["blocks"] for i in b["items"]}
    assert "weg" not in keys and "geheim" not in keys


def test_proposal_keeps_the_column_count_for_few_symbols_and_adds_ap_note():
    doc = propose([row("schalter", ["schalter"], mountings={"UP": 1, "AP": 1})], CATS, False, {}, "L",
                  style={"columns": 2})
    assert doc["style"]["columns"] == 2
    assert [n["text"] for n in doc["blocks"][0]["items"] if n["kind"] == "note"] == [AP_NOTE]


def test_v1_document_is_migrated_free_texts_become_entries():
    old = {"version": 1, "style": {"text_size": 3.0, "page_columns": 5},
           "title": {"text": "L", "x": 3, "y": 4, "size": 5},
           "blocks": [{"id": "a", "title": "Licht", "x": 10, "y": 20, "columns": 1, "items": [
               {"id": "i", "kind": "symbol", "symbol_key": "k", "x": 1, "y": 2, "scale": 3, "text_size": 7}]}],
           "texts": [{"id": "t", "text": "Hinweis Baustelle", "x": 1, "y": 1, "size": 9}]}
    doc = normalize(old)
    assert doc["version"] == 4 and doc["style"]["text_size"] == 3.0 and doc["style"]["columns"] == 2
    assert "x" not in doc["blocks"][0]["items"][0] and "scale" not in doc["blocks"][0]["items"][0]
    assert doc["blocks"][-1]["title"] == "Zusatztext"
    assert doc["blocks"][-1]["items"][0] == {**doc["blocks"][-1]["items"][0], "kind": "text", "text": "Hinweis Baustelle"}


# -- grid layout ------------------------------------------------------------------------

@pytest.mark.parametrize("columns", [2, 3])
def test_layout_stays_in_200mm_uses_the_columns_and_never_overlaps(columns):
    doc = normalize({"style": {"columns": columns}, "title": {"text": "Legende"},
                     "blocks": [block("A", 7, "Decken- / Wand-Leuchte mit Abdeckung und sehr langem Zusatz"),
                                block("B", 2)]})
    lay = layout(doc)
    assert lay["width"] <= 200
    items = boxes(lay)
    assert all(b["x"] >= 5 and b["x"] + b["w"] <= 195 + 1e-6 for b in items)
    xs = {round(b["x"], 2) for b in items if b["block"] == "A"}
    assert len(xs) == columns
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            assert not overlap(a, b), (a, b)
    for t in [p for p in lay["prims"] if p["t"] == "text" and not p["bold"]]:
        box = next(b for b in items if b["y"] <= t["y"] <= b["y"] + b["h"] and b["x"] <= t["x"] <= b["x"] + b["w"])
        assert t["x"] + text_width(t["text"], t["size"]) <= box["x"] + box["w"] + 1e-6


def test_height_grows_with_the_number_of_symbols_and_general_part_is_on_top():
    small = layout(normalize({"blocks": [block("A", 2)]}))
    big = layout(normalize({"blocks": [block("A", 30)]}))
    assert big["height"] > small["height"] + 40
    lay = layout(normalize({"blocks": [block("A", 2)]}), general={"w": 190, "h": 30})
    gen = next(p for p in lay["prims"] if p.get("role") == "general")
    first_block = boxes(lay, "block")[0]
    assert gen["y"] == 5 and first_block["y"] >= gen["y"] + gen["h"]
    assert lay["height"] > small["height"] + 30


def test_sections_by_default_have_only_a_header_bar_on_white_paper():
    doc = normalize({"version": 3, "blocks": [{"id": "k", "title": "Kraft", "style": section_style("#e03131"),
                                               "items": [{"id": "l", "kind": "line", "text": "AP-Leitung"}]}]})
    lay = layout(doc)
    roles = {p.get("role"): p for p in lay["prims"] if p["t"] == "rect"}
    assert roles["header"]["fill"] == "#e03131" and set(roles) == {"header"}
    head_text = next(p for p in lay["prims"] if p["t"] == "text" and p["bold"])
    assert head_text["color"] == "#ffffff"
    assert all(p["color"] == "#000000" for p in lay["prims"] if p["t"] == "text" and not p["bold"])
    doc["blocks"][0]["style"].update(background_on=True, border_on=True)
    roles = {p.get("role"): p for p in layout(doc)["prims"] if p["t"] == "rect"}
    assert roles["background"]["fill"] == section_style("#e03131")["background"]
    assert roles["border"]["stroke"] == "#e03131"
    light = section_style("#ffd43b")
    assert light["header_text"] == "#000000"


def test_older_documents_lose_the_filled_area_and_symbols_take_the_section_colour():
    old = {"version": 2, "blocks": [{"id": "a", "title": "Leitungen", "style": {
        "header": "#707888", "background": "#f0f1f3", "border_on": True, "symbol": "#707888"}, "items": []}]}
    st = normalize(old)["blocks"][0]["style"]
    assert st["background_on"] is False and st["border_on"] is False and st["symbol"] == "#707888"
    assert st["header"] == "#707888"
    neutral = normalize({"version": 3, "blocks": [{"id": "a", "title": "Ohne", "style": section_style(None),
                                                   "items": []}]})["blocks"][0]["style"]
    assert neutral["symbol"] == "#000000"                       # no plan colour: black, not grey


def _sym_block(sizes_list, rotation=None):
    items = [{"id": f"s{k}", "kind": "symbol", "symbol_key": f"k{k}", "text": f"Symbol {k} mit Text"}
             for k in range(len(sizes_list))]
    if rotation:
        items[rotation[0]]["rotation"] = rotation[1]
    doc = normalize({"version": 3, "style": {"columns": 2},
                     "blocks": [{"id": "S", "title": "Schalter und Taster", "items": items}]})
    sizes = {f"s{k}": sz for k, sz in enumerate(sizes_list)}
    return doc, sizes


def _columns(lay):
    syms = [p for p in lay["prims"] if p["t"] == "symbol"]
    texts = [p for p in lay["prims"] if p["t"] == "text" and not p["bold"]]
    return syms, texts


def test_symbol_centres_share_one_axis_and_texts_one_line_per_column():
    # Bewegungsmelder, Drehschalter, Präsenzmelder: different widths
    doc, sizes = _sym_block([(4.0, 4.0, False), (9.0, 4.0, False), (2.0, 3.5, False), (6.0, 4.5, False),
                             (3.0, 3.0, False), (7.5, 4.0, False)])
    lay = layout(doc, sizes)
    syms, texts = _columns(lay)
    hits = boxes(lay)
    for col_x in {round(h["x"], 3) for h in hits}:
        col = [h["id"] for h in hits if round(h["x"], 3) == col_x]
        cxs = {s["cx"] for s in syms if s["id"] in col}
        txs = {t["x"] for t in texts if t["item"] in col}
        assert len(cxs) == 1 and len(txs) == 1
        cx, tx = cxs.pop(), txs.pop()
        assert all(tx >= s["cx"] + s["w"] / 2 + 1.0 for s in syms if s["id"] in col)   # wide one pushes nobody
    for s in syms:
        t = next(t for t in texts if t["item"] == s["id"])
        mid_text = t["y"] - t["size"] * 0.32
        assert abs(mid_text - s["cy"]) < 0.01                         # same horizontal middle


def test_turning_a_symbol_keeps_centre_and_text_line_and_grows_the_row():
    doc, sizes = _sym_block([(12.0, 2.0, False), (4.0, 4.0, False), (4.0, 4.0, False), (4.0, 4.0, False)])
    flat = layout(doc, sizes)
    doc_t, _ = _sym_block([(12.0, 2.0, False), (4.0, 4.0, False), (4.0, 4.0, False), (4.0, 4.0, False)], rotation=(0, 90))
    turned = layout(doc_t, sizes)
    a = next(p for p in flat["prims"] if p["t"] == "symbol" and p["id"] == "s0")
    b = next(p for p in turned["prims"] if p["t"] == "symbol" and p["id"] == "s0")
    assert b["rot"] == 90 and b["w"] < b["h"] and b["cx"] == next(
        p for p in turned["prims"] if p["t"] == "symbol" and p["id"] == "s1")["cx"]
    hit = next(h for h in boxes(turned) if h["id"] == "s0")
    assert hit["h"] >= b["h"] and b["cy"] - b["h"] / 2 >= hit["y"] - 1e-6
    t = next(p for p in turned["prims"] if p["t"] == "text" and p.get("item") == "s0")
    assert t["x"] >= b["cx"] + b["w"] / 2 and abs(t["y"] - t["size"] * 0.32 - b["cy"]) < 0.01
    assert a["h"] < b["h"]
    items = boxes(turned)
    for i, x in enumerate(items):
        for y in items[i + 1:]:
            assert not overlap(x, y)


def test_text_factor_changes_only_that_text_and_the_row_grows():
    doc = normalize({"version": 3, "blocks": [block("A", 3)]})
    doc["style"]["symbol_size"] = "real"                             # real size on the insertion point
    base = layout(doc)
    doc["blocks"][0]["items"][1]["text_scale"] = 1.2
    big = layout(doc)
    sizes = {t["item"]: t["size"] for t in big["prims"] if t["t"] == "text" and t.get("item")}
    assert sizes["A1"] == 3.0 and sizes["A0"] == 2.5 and sizes["A2"] == 2.5
    doc["blocks"][0]["items"][1]["text"] = "Langer Text " * 8
    grown = layout(doc)
    h = {b["id"]: b["h"] for b in boxes(grown)}
    assert h["A1"] > h["A0"]
    doc["style"]["text_size"] = 3.0
    common = {t["item"]: t["size"] for t in layout(doc)["prims"] if t["t"] == "text" and t.get("item")}
    assert common["A0"] == 3.0 and common["A1"] == 3.6
    assert base["height"] <= big["height"]


def test_gap_between_sections_moves_only_the_sections():
    doc = normalize({"version": 3, "blocks": [block("A", 4), block("B", 4)]})

    def sections(d):
        return {s["id"]: s for s in boxes(layout(d), "section")}

    s0 = sections(doc)
    assert abs(s0["B"]["y"] - (s0["A"]["y"] + s0["A"]["h"])) < 1e-6           # 0: they touch
    doc["style"]["section_gap"] = 6
    s6 = sections(doc)
    assert abs(s6["B"]["y"] - (s6["A"]["y"] + s6["A"]["h"]) - 6) < 1e-6
    assert s6["A"]["h"] == s0["A"]["h"] and s6["B"]["h"] == s0["B"]["h"]     # rows inside unchanged


def test_hidden_entries_are_not_placed():
    doc = normalize({"version": 3, "blocks": [block("A", 3)]})
    doc["blocks"][0]["items"][0]["hidden"] = True
    assert "A0" not in {b["id"] for b in boxes(layout(doc))}
    assert normalize(doc)["blocks"][0]["items"][0]["hidden"] is True


def test_wrap_keeps_words_and_cuts_only_long_ones():
    lines = wrap("Decken- / Wand-Leuchte mit Abdeckung", 2.5, 30)
    assert len(lines) >= 2 and all(text_width(line, 2.5) <= 30 for line in lines)
    assert wrap("", 2.5, 30) == [""]
    assert all(text_width(line, 2.5) <= 10 for line in wrap("Donaudampfschifffahrt", 2.5, 10))


def test_luminaire_length_changes_the_drawing():
    content = "2DNeutral;Typ=0;A=*L;B=*;A1=0;B1=0;Lines=3"
    short = geometry_bounds(engine_geometry(content, {"L": "600", "B": "600"}))
    long = geometry_bounds(engine_geometry(content, {"L": "1500", "B": "300"}))
    assert round((long[2] - long[0]) / (short[2] - short[0]), 2) == 2.5


# -- routes ---------------------------------------------------------------------------------

def _project(client, tmp, name="Test"):
    pid = client.post("/api/projects", json={"name": name, "project_number": "1424"}).json()["id"]
    import_dxf(client, pid, nova_like_dxf(tmp / f"{name}.dxf"))
    return pid


def test_legend_roundtrip_layout_and_texts(env):  # noqa: F811
    client, tmp = env
    pid = _project(client, tmp)
    info = client.get(f"/api/projects/{pid}/legend").json()
    assert info["legend"] is None and info["style"]["text_size"] == 2.5 and info["grids"][0]["id"] == "standard"
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    assert doc["title"]["text"] == "Legende 1424 Test"
    saved = client.put(f"/api/projects/{pid}/legend", json={"doc": doc}).json()["legend"]
    assert saved["updated_by"] and client.get(f"/api/projects/{pid}/legend").json()["legend"]["doc"] == saved["doc"]
    lay = client.post(f"/api/projects/{pid}/legend/layout", json={"doc": saved["doc"]}).json()
    assert lay["width"] <= 200 and any(p["t"] == "symbol" for p in lay["prims"])
    assert lay["general"]["kind"] == ""


def test_new_project_starts_with_company_standard_template_wins_and_remember(env, monkeypatch):  # noqa: F811
    client, tmp = env
    monkeypatch.setattr(config, "current_user", lambda: "chef")
    assert client.put("/api/company/legend", json={"admins": ["chef"], "text_size": 3.0, "symbol_scale": 0.8}).status_code == 200
    a = _project(client, tmp, "A")
    assert client.get(f"/api/projects/{a}/legend").json()["style"]["text_size"] == 3.0
    doc = client.post(f"/api/projects/{a}/legend/propose").json()["doc"]
    assert doc["style"]["symbol_scale"] == 0.8
    doc["style"]["text_size"] = 3.5
    doc["style"]["columns"] = 3
    client.put(f"/api/projects/{a}/legend", json={"doc": doc})
    b = client.post("/api/projects", json={"name": "B", "template": a}).json()["id"]
    bl = client.get(f"/api/projects/{b}/legend").json()
    assert bl["legend"]["doc"]["style"]["text_size"] == 3.5 and bl["style"]["columns"] == 3   # legend copied
    other = client.post("/api/projects", json={"name": "C"}).json()["id"]
    assert client.get(f"/api/projects/{other}/legend").json()["style"]["text_size"] == 3.0
    client.post(f"/api/projects/{a}/legend/remember", json={"doc": doc})
    assert client.get("/api/company/legend").json()["text_size"] == 3.5
    assert client.get(f"/api/projects/{other}/legend").json()["style"]["text_size"] == 3.0   # existing unchanged
    d = client.post("/api/projects", json={"name": "D"}).json()["id"]
    assert client.get(f"/api/projects/{d}/legend").json()["style"]["text_size"] == 3.5


def test_only_admins_change_company_legend_settings(env, monkeypatch):  # noqa: F811
    client, tmp = env
    monkeypatch.setattr(config, "current_user", lambda: "chef")
    assert client.get("/api/company/legend").json()["bootstrap"] is True
    assert client.put("/api/company/legend", json={"admins": ["jemand"]}).status_code == 400   # no self lock-out
    assert client.put("/api/company/legend", json={"admins": ["Chef"]}).status_code == 200
    monkeypatch.setattr(config, "current_user", lambda: "maria")
    info = client.get("/api/company/legend").json()
    assert info["is_admin"] is False and info["admins"] == ["Chef"]
    assert client.put("/api/company/legend", json={"general_path": "x.dxf"}).status_code == 403
    pid = _project(client, tmp)
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    assert client.post(f"/api/projects/{pid}/legend/remember", json={"doc": doc}).status_code == 403


def _template_dxf(path):
    doc = ezdxf.new("R2013", units=4)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (180, 0), (180, 25), (0, 25)], close=True)
    msp.add_text("Allgemein edeco", height=3).set_placement((5, 10))
    doc.saveas(path)
    return path


def test_general_part_from_dxf_is_on_top_and_n4d_is_refused(env, monkeypatch, tmp_path):  # noqa: F811
    client, tmp = env
    monkeypatch.setattr(config, "current_user", lambda: "chef")
    tpl = _template_dxf(tmp_path / "allgemein.dxf")
    info = client.put("/api/company/legend", json={"general_path": str(tpl)}).json()
    assert info["general"]["kind"] == "dxf" and round(info["general"]["h"]) == 25
    pid = _project(client, tmp)
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    lay = client.post(f"/api/projects/{pid}/legend/layout", json={"doc": doc}).json()
    gen = next(p for p in lay["prims"] if p.get("role") == "general")
    assert gen["y"] == 5 and min(p["y"] for p in lay["prims"] if p["t"] == "hit" and p["kind"] == "block") > 30
    assert client.get(f"/api/projects/{pid}/legend/general").json()["svg"].startswith("<svg")
    n4d = tmp_path / "Legende.n4d"
    n4d.write_bytes(b"x")
    info = client.put("/api/company/legend", json={"general_path": str(n4d)}).json()
    assert info["general"]["kind"] == "" and "DXF- oder DWG" in info["general"]["error"]


def test_general_part_from_a_template_project(env, monkeypatch):  # noqa: F811
    client, tmp = env
    monkeypatch.setattr(config, "current_user", lambda: "chef")
    tpl = _project(client, tmp, "Vorlage Allgemein")
    tdoc = client.post(f"/api/projects/{tpl}/legend/propose").json()["doc"]
    client.put(f"/api/projects/{tpl}/legend", json={"doc": tdoc})
    folder = client.get(f"/api/projects/{tpl}").json()["folder"]
    info = client.put("/api/company/legend", json={"general_path": folder}).json()
    assert info["general"]["kind"] == "project" and info["general"]["h"] > 10
    prev = client.get(f"/api/projects/{tpl}/legend/general").json()
    assert prev["prims"] and all(p["t"] != "hit" for p in prev["prims"])


def test_export_dxf_whole_and_one_category_with_and_without_general(env, monkeypatch, tmp_path):  # noqa: F811
    client, tmp = env
    monkeypatch.setattr(config, "current_user", lambda: "chef")
    client.put("/api/company/legend", json={"general_path": str(_template_dxf(tmp_path / "a.dxf"))})
    pid = _project(client, tmp)
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    doc["blocks"][0]["style"]["header"] = "#e03131"
    doc = client.put(f"/api/projects/{pid}/legend", json={"doc": doc}).json()["legend"]["doc"]
    target = doc["blocks"][0]

    def fetch(**params):
        res = client.get(f"/api/projects/{pid}/legend/export", params=params)
        assert res.status_code == 200, res.text
        path = tmp_path / "out.dxf"
        path.write_bytes(res.content)
        return res, ezdxf.readfile(path)

    res, whole = fetch(format="dxf")
    assert "Legende.dxf" in res.headers["content-disposition"]
    assert whole.dxfversion == "AC1027"
    assert "Allgemeinteil" in whole.blocks
    colors = {e.rgb for e in whole.modelspace() if e.dxf.hasattr("true_color")}
    assert (0xE0, 0x31, 0x31) in colors
    assert any(e.dxftype() == "INSERT" and e.dxf.name != "Allgemeinteil" for e in whole.modelspace())
    res, only = fetch(format="dxf", block=target["id"], general="false")
    assert "Allgemeinteil" not in [i.dxf.name for i in only.modelspace().query("INSERT")]
    assert target["title"].replace(" ", "%20") in res.headers["content-disposition"] or \
        target["title"] in res.headers["content-disposition"]
    titles = [t.dxf.text for t in only.modelspace().query("TEXT")]
    other = [b["title"] for b in doc["blocks"][1:]]
    assert target["title"] in titles and not any(o in titles for o in other)
    _, with_general = fetch(format="dxf", block=target["id"], general="true")
    assert "Allgemeinteil" in [i.dxf.name for i in with_general.modelspace().query("INSERT")]
    no_oda = client.get(f"/api/projects/{pid}/legend/export", params={"format": "dwg"})
    if not config.find_oda_converter():
        assert no_oda.status_code == 400 and "ODA File Converter" in no_oda.json()["detail"]


def test_company_description_is_used_for_new_proposals(env):  # noqa: F811
    client, tmp = env
    pid = _project(client, tmp)
    fam = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]["blocks"][0]["items"][0]["family_key"]
    assert client.put("/api/descriptions", json={"family_key": fam, "text": "Firmentext A"}).json()["text"] == "Firmentext A"
    texts = [i["text"] for b in client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]["blocks"]
             for i in b["items"]]
    assert "Firmentext A" in texts
    assert client.get(f"/api/projects/{pid}/legend").json()["descriptions"][fam] == "Firmentext A"
    sug = client.get("/api/legend/texts", params={"q": "Brandmelder", "family_key": fam}).json()["items"]
    assert sug[0] == {"text": "Firmentext A", "score": 100, "source": "Firmentext"}
    assert any(s["text"] == "Brandmelder / Indikator" for s in sug)


def test_empty_doc_defaults():
    doc = empty_doc()
    assert doc["style"]["width"] == 200 and doc["style"]["grid"] == "standard"
    assert doc["style"]["row"] == 4.55 and doc["style"]["text_offset"] == 9.75 and doc["style"]["columns"] == 2


# -- symbol colours, general part contents, export details ---------------------------------

def _coloured_symbol():
    from nova_legend.parser.geometry import Primitive, SymbolGeometry

    square = {"points": [(-0.002, -0.002), (0.002, -0.002), (0.002, 0.002), (-0.002, 0.002)],
              "closed": True, "segments": []}
    return SymbolGeometry(primitives=[
        Primitive("line", "X", False, {"start": (-0.003, 0.0), "end": (0.003, 0.0)}),            # no own colour
        Primitive("polygon", "X", True, square, color="#ff0000"),                                 # red area
    ])


def test_symbols_keep_own_colours_and_take_the_section_colour_elsewhere():
    from nova_legend.legend.export import build_dxf
    from nova_legend.render.svg import render_svg

    geo = _coloured_symbol()
    svg = render_svg(geo, None, show_points=False, own_colors=True)
    # no own colour: the page colour (= section colour); own colour: stays
    assert 'stroke="currentColor"' in svg and 'fill="#ff0000"' in svg
    doc = normalize({"version": 3, "blocks": [{"id": "b", "title": "Licht", "style": section_style("#0000ff"),
                                               "items": [{"id": "i", "kind": "symbol", "symbol_key": "k",
                                                          "text": "Leuchte", "rotation": 90}]}]})
    lay = layout(doc, {"i": (6.0, 4.0, False)})
    dxf = build_dxf(lay, None, lambda prim: geo)
    ins = next(e for e in dxf.modelspace().query("INSERT"))
    assert not ins.dxf.hasattr("true_color") and ins.dxf.rotation == 90
    colours = {e.rgb for e in dxf.blocks[ins.dxf.name] if e.dxf.hasattr("true_color")}
    assert (0, 0, 255) in colours and (255, 0, 0) in colours            # section blue, own red
    sym = next(p for p in lay["prims"] if p["t"] == "symbol")
    # the turned block keeps its centre on the axis of the column
    x0, y0, x1, y1 = geometry_bounds(geo)
    assert abs(ins.dxf.insert.x - sym["cx"]) < 1e-3 and abs(ins.dxf.insert.y - (lay["height"] - sym["cy"])) < 1e-3


def test_covered_by_the_general_part_by_text_or_symbol():
    from nova_legend.api.legend import covered_families
    from nova_legend.legend.general import GeneralPart, norm_text

    rows = [row("oben", ["allgemein"]), row("dose", ["allgemein"]), row("fast", ["allgemein"])]
    rows[0]["title"] = "Leitung, nach oben"
    rows[2]["title"] = "Leitung nach oben rechts"      # only similar: stays
    dxf = GeneralPart(kind="dxf", texts=[norm_text("Leitung nach oben"), norm_text("Abzweigdose")])
    assert covered_families(dxf, rows, {"dose": "Abzweigdose"}) == {"oben", "dose"}
    proj = GeneralPart(kind="project", symbol_keys=["sym:fast"])
    assert covered_families(proj, rows, {}) == {"fast"}
    doc = propose(rows, CATS, True, {}, "L", covered={"oben", "dose"})
    assert [i["family_key"] for b in doc["blocks"] for i in b["items"]] == ["fast"]


def test_general_part_entries_are_left_out_of_the_proposal(env, monkeypatch, tmp_path):  # noqa: F811
    client, tmp = env
    monkeypatch.setattr(config, "current_user", lambda: "chef")
    pid = _project(client, tmp)
    first = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]["blocks"][0]["items"][0]
    tpl = ezdxf.new("R2013", units=4)
    blk = tpl.blocks.new("Zeile")
    blk.add_text(first["text"].upper() + ",", height=2.5).set_placement((10, 0))
    tpl.modelspace().add_blockref("Zeile", (0, 0))
    tpl.modelspace().add_line((0, -5), (180, -5))
    tpl.saveas(tmp_path / "allg.dxf")
    client.put("/api/company/legend", json={"general_path": str(tmp_path / "allg.dxf")})
    info = client.get(f"/api/projects/{pid}/legend").json()
    assert first["family_key"] in info["in_general"]["covered"]
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    assert first["family_key"] not in {i["family_key"] for b in doc["blocks"] for i in b["items"]}


def test_export_without_general_has_no_general_block_and_a_named_path(env, monkeypatch, tmp_path):  # noqa: F811
    client, tmp = env
    monkeypatch.setattr(config, "current_user", lambda: "chef")
    client.put("/api/company/legend", json={"general_path": str(_template_dxf(tmp_path / "a.dxf"))})
    pid = _project(client, tmp)
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    doc = client.put(f"/api/projects/{pid}/legend", json={"doc": doc}).json()["legend"]["doc"]
    block_id = doc["blocks"][0]["id"]
    name = client.get(f"/api/projects/{pid}/legend/export-name", params={"block": block_id}).json()["name"]
    assert name == f"edeco ag-Test-{doc['blocks'][0]['title']}.dxf"
    assert client.get(f"/api/projects/{pid}/legend/export-name").json()["name"] == "edeco ag-Test-Legende.dxf"
    res = client.get(f"/api/projects/{pid}/legend/export/{name}", params={"block": block_id, "general": "false"})
    assert res.status_code == 200
    (tmp_path / "o.dxf").write_bytes(res.content)
    out = ezdxf.readfile(tmp_path / "o.dxf")
    assert "Allgemeinteil" not in out.blocks
    res = client.get(f"/api/projects/{pid}/legend/export/x.dxf", params={"general": "true"})
    (tmp_path / "g.dxf").write_bytes(res.content)
    assert "Allgemeinteil" in ezdxf.readfile(tmp_path / "g.dxf").blocks


def test_gap_is_the_same_in_the_dxf(tmp_path):
    from nova_legend.legend.export import build_dxf

    def header_tops(gap):
        doc = normalize({"version": 3, "style": {"section_gap": gap},
                         "blocks": [block("A", 2), block("B", 2)]})
        for b in doc["blocks"]:
            b["style"]["header"] = "#e03131"
        lay = layout(doc)
        dxf = build_dxf(lay, None, lambda p: None)
        tops = sorted(max(v[1] for v in h.paths[0].vertices) for h in dxf.modelspace().query("HATCH")
                      if h.rgb == (0xE0, 0x31, 0x31))
        return [lay["height"] - t for t in tops][::-1]

    a, b = header_tops(0), header_tops(4)
    assert abs((b[1] - b[0]) - (a[1] - a[0]) - 4) < 1e-3


def test_entries_share_one_tile_sized_from_the_text():
    doc, sizes = _sym_block([(4.0, 4.0, False), (9.0, 7.0, False), (40.0, 4.0, False), (6.0, 4.5, False)],
                            rotation=(3, 90))
    doc["blocks"][0]["items"][2]["text"] = "Sehr langer Text, der in seiner Spalte umbrechen muss " * 2
    doc["style"]["symbol_size"] = "tile"                             # equal tiles
    lay = layout(doc, sizes)
    hits = boxes(lay)
    assert len({round(h["h"], 3) for h in hits}) == 1
    syms = [p for p in lay["prims"] if p["t"] == "symbol"]
    tile = round(2.5 * 3.6, 3)                                         # text 2.5 mm → one tile
    assert {round(max(s["w"], s["h"]), 3) for s in syms} == {round(tile * 0.75, 3)}   # 75 % of the tile
    long = next(s for s in syms if s["id"] == "s2")                    # 40 × 4 mm light
    assert long["w"] / long["h"] == pytest.approx(10, rel=0.05)
    grid = next(p for p in lay["prims"] if p["t"] == "grid")
    assert all(abs(s["cx"] - (grid["x"] + grid["axis"]) - k * grid["colw"]) < 1e-6
               for s in syms for k in [round((s["cx"] - grid["x"] - grid["axis"]) / grid["colw"])])


def test_every_symbol_is_centred_in_the_same_tile_and_texts_share_one_line():
    items = [{"id": f"s{k}", "kind": "symbol", "symbol_key": f"k{k}", "text": f"Steckdose {k}"} for k in range(4)]
    doc = normalize({"version": 3, "style": {"columns": 2}, "blocks": [{"id": "S", "title": "Dosen", "items": items}]})
    sizes = {"s0": (-2.0, -2.0, 4.5, 2.0, False),
             "s1": (-2.0, -2.0, 2.0, 2.0, False),
             "s2": (-1.0, -1.5, 1.0, 1.5, False),
             "s3": (3.0, 1.0, 7.0, 3.0, False)}
    doc["style"]["symbol_size"] = "tile"                             # equal tiles
    lay = layout(doc, sizes)
    syms = {p["id"]: p for p in lay["prims"] if p["t"] == "symbol"}
    texts = {p["item"]: p for p in lay["prims"] if p["t"] == "text" and p.get("item")}
    assert syms["s0"]["cx"] == syms["s1"]["cx"]
    assert texts["s0"]["x"] == texts["s1"]["x"]
    assert texts["s0"]["y"] == texts["s2"]["y"]
    tile = round(2.5 * 3.6, 3)
    assert {round(max(s["w"], s["h"]), 3) for s in syms.values()} == {round(tile * 0.75, 3)}      # 75 % of the tile


def test_symbol_factor_enlarges_only_that_symbol_and_the_row_grows():
    doc, sizes = _sym_block([(4.0, 4.0, False), (4.0, 4.0, False), (4.0, 4.0, False), (4.0, 4.0, False)])
    doc["style"]["symbol_size"] = "real"                             # real size on the insertion point
    base = {p["id"]: p for p in layout(doc, sizes)["prims"] if p["t"] == "symbol"}
    doc["blocks"][0]["items"][0]["symbol_factor"] = 1.5
    lay = layout(doc, sizes)
    big = {p["id"]: p for p in lay["prims"] if p["t"] == "symbol"}
    assert abs(big["s0"]["scale"] - base["s0"]["scale"] * 1.5) < 1e-3 and big["s1"]["scale"] == base["s1"]["scale"]
    rows = {h["id"]: round(h["h"] / 4.55) for h in boxes(lay)}
    assert rows["s0"] == 2 and rows["s1"] == 1
    assert normalize(doc)["blocks"][0]["items"][0]["symbol_factor"] == 1.5


def test_title_size_and_border_and_a_frame_round_the_legend():
    doc = normalize({"version": 3, "title": {"text": "Legende 1424", "scale": 1.6, "border_on": True},
                     "style": {"frame_on": True}, "blocks": [block("A", 2)]})
    lay = layout(doc)
    title = next(p for p in lay["prims"] if p["t"] == "text" and p["text"] == "Legende 1424")
    assert title["size"] == 4.0
    frame = next(p for p in lay["prims"] if p.get("block") == "title" and p["t"] == "rect")
    assert frame["y"] <= title["y"] - title["size"] and title["y"] <= frame["y"] + frame["h"]
    hit = next(p for p in lay["prims"] if p["t"] == "hit" and p["kind"] == "title")
    assert hit["h"] == frame["h"]
    outer = next(p for p in lay["prims"] if p.get("block") == "frame")
    assert outer["x"] == 2.5 and abs(outer["y"] + outer["h"] - (lay["height"] - 2.5)) < 1e-6
    first = boxes(lay, "block")[0]
    assert first["y"] > frame["y"] + frame["h"]
    doc["title"]["border_on"] = False
    doc["style"]["frame_on"] = False
    assert not [p for p in layout(doc)["prims"] if p["t"] == "rect" and p.get("block") in ("title", "frame")]


def test_sheet_width_is_adjustable_standard_200_at_most_210():
    assert normalize({})["style"]["width"] == 200
    assert normalize({"style": {"width": 230}})["style"]["width"] == 210
    doc = normalize({"version": 3, "style": {"width": 210}, "blocks": [block("A", 6, "Text " * 6)]})
    lay = layout(doc)
    assert lay["width"] == 210
    assert max(h["x"] + h["w"] for h in boxes(lay)) <= 205 + 1e-6
    doc["style"]["width"] = 150
    narrow = layout(doc, general={"w": 180, "h": 30})
    gen = next(p for p in narrow["prims"] if p.get("role") == "general")
    assert narrow["width"] == 150 and gen["w"] == 140 and abs(gen["h"] - 30 * 140 / 180) < 1e-6
    assert gen["fit"] < 1


def test_narrow_sheet_shrinks_the_general_part_in_the_dxf(env, monkeypatch, tmp_path):  # noqa: F811
    client, tmp = env
    monkeypatch.setattr(config, "current_user", lambda: "chef")
    client.put("/api/company/legend", json={"general_path": str(_template_dxf(tmp_path / "a.dxf"))})
    pid = _project(client, tmp)
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    doc["style"]["width"] = 150
    client.put(f"/api/projects/{pid}/legend", json={"doc": doc})
    res = client.get(f"/api/projects/{pid}/legend/export", params={"general": "true"})
    (tmp_path / "n.dxf").write_bytes(res.content)
    out = ezdxf.readfile(tmp_path / "n.dxf")
    ins = next(i for i in out.modelspace().query("INSERT") if i.dxf.name == "Allgemeinteil")
    assert abs(ins.dxf.xscale - 140 / 180) < 1e-3


def test_release_check_lists_what_is_open(env, monkeypatch):  # noqa: F811
    client, tmp = env
    pid = _project(client, tmp)
    first = client.get(f"/api/projects/{pid}/review").json()
    ids = {c["id"]: c for c in first["checks"]}
    assert first["ready"] is False and ids["legend"]["level"] == "block"
    assert ids["unknown"]["level"] == "block" and ids["unknown"]["items"][0]["title"] == "Gateway"
    assert ids["unknown"]["target"] == "unknown"
    assert [c["level"] for c in first["checks"]] == sorted((c["level"] for c in first["checks"]),
                                                           key=["block", "warn", "ok"].index)
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    removed = doc["blocks"][0]["items"].pop(0)
    doc["blocks"][-1]["items"].append(dict(doc["blocks"][-1]["items"][0], id="twice"))
    client.put(f"/api/projects/{pid}/legend", json={"doc": doc})
    ids = {c["id"]: c for c in client.get(f"/api/projects/{pid}/review").json()["checks"]}
    assert "legend" not in ids
    assert ids["missing"]["level"] == "block" and ids["missing"]["count"] == 1
    row_titles = {r["family_key"]: r["title"] for r in client.get(f"/api/projects/{pid}").json()["rows"]}
    assert ids["missing"]["items"][0]["title"] == row_titles[removed["family_key"]]
    assert ids["duplicates"]["count"] == 1 and ids["outdated"]["level"] == "ok"
    # ignore the unknown element and complete the legend: ready
    gateway = client.get(f"/api/projects/{pid}").json()["unknown"][0]["source_key"]
    client.put("/api/mappings", json={"source_key": gateway, "symbol_key": "__ignore__", "name": "Gateway"})
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    client.put(f"/api/projects/{pid}/legend", json={"doc": doc})
    done = client.get(f"/api/projects/{pid}/review").json()
    blocking = [c["id"] for c in done["checks"] if c["level"] == "block"]
    assert done["ready"] is True and blocking == []


def test_fixed_text_lines_share_one_row_height_and_drop_the_extra_lines():
    doc = normalize({"version": 3, "style": {"text_lines": 2, "entry_gap": 1.5}, "blocks": [block("A", 3)]})
    doc["blocks"][0]["items"][1]["text"] = "Langer Text " * 12
    lay = layout(doc)
    heights = [round(h["h"], 3) for h in boxes(lay)]
    assert len(set(heights)) == 1
    lines = [t for t in lay["prims"] if t["t"] == "text" and t.get("item") == "A1"]
    assert 1 <= len(lines) <= 2


def test_linear_symbol_keeps_its_proportion():
    items = [{"id": "s0", "kind": "symbol", "symbol_key": "k", "text": "Langfeld"}]
    doc = normalize({"version": 3, "blocks": [{"id": "S", "title": "Licht", "items": items}]})
    lay = layout(doc, {"s0": (40.0, 4.0, False)})
    sym = next(p for p in lay["prims"] if p["t"] == "symbol")
    assert sym["w"] / sym["h"] == pytest.approx(10, rel=0.05)
    assert sym["w"] > sym["h"] * 2


def test_symbol_on_two_layers_is_proposed_in_both_categories():
    sample = row("leuchte", ["schalter"])
    sample["layers"] = {"E_Licht": 2, "E_Starkstrom": 1}
    doc = propose([sample], CATS, True, {}, "L",
                  layer_categories={"E_Licht": "schalter", "E_Starkstrom": "allgemein"})
    placed = {(b["category_id"], i["family_key"]) for b in doc["blocks"] for i in b["items"] if i["kind"] == "symbol"}
    assert placed == {("schalter", "leuchte"), ("allgemein", "leuchte")}


def test_diagnostics_report_has_no_geometry(env):
    client, _folder = env
    res = client.get("/api/diagnostics")
    assert res.status_code == 200
    body = res.json()
    assert body["programm"] == "edeco ag - NOVA Legenden"
    assert "svg" not in body


def test_automatic_text_lines_never_cut_a_long_text():
    long = ("Steckdose T13, 3-fach, geschaltet, mit Kinderschutz und Deckel für Feuchtraum IP55 in "
            "Aufputz-Ausführung, Farbe weiss, Montage auf Brüstungskanal neben dem Arbeitsplatz")
    doc = normalize({"version": 3, "blocks": [{"id": "A", "title": "A", "items": [
        {"id": "s", "kind": "symbol", "symbol_key": "k", "text": long},
        {"id": "t", "kind": "symbol", "symbol_key": "k2", "text": "Taster"}]}]})
    assert doc["style"]["text_lines"] == 0
    lay = layout(doc, {"s": (-2.5, 0, 2.5, 5, False), "t": (-2.5, 0, 2.5, 5, False)})
    shown = " ".join(p["text"] for p in lay["prims"] if p["t"] == "text" and p.get("item") == "s")
    assert shown.split() == long.split()                                    # every word is on the sheet
    rows = {h["id"]: h for h in boxes(lay)}
    assert rows["s"]["h"] > rows["t"]["h"]                                  # the long text's row grows
    for t in [p for p in lay["prims"] if p["t"] == "text" and p.get("item") == "s"]:
        assert rows["s"]["y"] <= t["y"] - t["size"] and t["y"] <= rows["s"]["y"] + rows["s"]["h"]


def test_entries_fill_whole_grid_rows_of_their_section():
    doc, sizes = _sym_block([(4.0, 4.0, False), (9.0, 7.0, False), (2.0, 3.5, False), (6.0, 4.5, False)],
                            rotation=(3, 90))
    doc["blocks"][0]["items"][2]["text"] = "Sehr langer Text, der in seiner Spalte umbrechen muss " * 2
    doc["blocks"][0]["items"][0]["text_scale"] = 1.2
    doc["style"]["symbol_size"] = "real"                             # real size on the insertion point
    lay = layout(doc, sizes)
    grid = next(p for p in lay["prims"] if p["t"] == "grid")
    row = grid["row"]
    for h in boxes(lay):
        k = h["h"] / row
        assert abs(k - round(k)) < 1e-6 and k >= 1                       # whole rows
        off = (h["y"] - grid["y"]) / row
        assert abs(off - round(off)) < 1e-6                              # starts on a grid line
        assert grid["y"] <= h["y"] and h["y"] + h["h"] <= grid["y"] + grid["h"] + 1e-6
    syms = [p for p in lay["prims"] if p["t"] == "symbol"]
    assert {s["scale"] for s in syms} == {1.0}                          # same scale, same size
    tall = next(s for s in syms if s["id"] == "s1")                      # 7 mm high: two rows
    assert next(h for h in boxes(lay) if h["id"] == "s1")["h"] == 2 * row and tall["h"] == 7.0
    col0 = grid["x"]
    assert all(abs(s["cx"] - (col0 + grid["axis"]) - k * grid["colw"]) < 1e-6
               for s in syms for k in [round((s["cx"] - col0 - grid["axis"]) / grid["colw"])])


def test_insertion_points_sit_on_the_axis_and_texts_start_right_of_the_widest_part():
    # Steckdose T13 with a "3" on the right: the drawing reaches further right of the insertion point
    items = [{"id": f"s{k}", "kind": "symbol", "symbol_key": f"k{k}", "text": f"Steckdose {k}"} for k in range(4)]
    doc = normalize({"version": 3, "style": {"columns": 2}, "blocks": [{"id": "S", "title": "Dosen", "items": items}]})
    sizes = {"s0": (-2.0, -2.0, 4.5, 2.0, False),      # label on the right
             "s1": (-2.0, -2.0, 2.0, 2.0, False),      # centred
             "s2": (-1.0, -1.5, 1.0, 1.5, False),
             "s3": (3.0, 1.0, 7.0, 3.0, False)}        # insertion point outside: the middle is used
    doc["style"]["symbol_size"] = "real"                             # real size on the insertion point
    lay = layout(doc, sizes)
    syms = {p["id"]: p for p in lay["prims"] if p["t"] == "symbol"}
    texts = {p["item"]: p for p in lay["prims"] if p["t"] == "text" and p.get("item")}
    assert syms["s0"]["cx"] == syms["s1"]["cx"] and (syms["s0"]["ax"], syms["s0"]["ay"]) == (0, 0)
    assert (syms["s3"]["ax"], syms["s3"]["ay"]) == (5.0, 2.0)
    assert texts["s0"]["x"] == texts["s1"]["x"]
    assert texts["s0"]["x"] >= syms["s0"]["x0"] + syms["s0"]["w"] + 1.0          # right of the "3"
    assert syms["s0"]["x0"] < syms["s0"]["cx"] - 1.9                              # drawing not re-centred


def test_mirror_and_45_degree_steps_keep_the_symbol_in_its_tile_and_dxf():
    from nova_legend.legend.export import build_dxf

    doc, sizes = _sym_block([(6.0, 2.0, False), (4.0, 4.0, False), (4.0, 4.0, False), (4.0, 4.0, False)])
    doc["blocks"][0]["items"][0].update(rotation=45, mirror=True)
    doc = normalize(doc)
    assert doc["blocks"][0]["items"][0]["rotation"] == 45 and doc["blocks"][0]["items"][0]["mirror"] is True
    lay = layout(doc, sizes)
    sym = next(p for p in lay["prims"] if p["t"] == "symbol" and p["id"] == "s0")
    assert sym["rot"] == 45 and sym["mirror"] is True
    tile = round(2.5 * 3.6, 3)
    assert max(sym["w"], sym["h"]) <= tile * 0.75 + 1e-6               # turned drawing still fits
    dxf = build_dxf(lay, None, lambda prim: _coloured_symbol())
    ins = next(e for e in dxf.modelspace().query("INSERT") if e.dxf.rotation == 45)
    assert ins.dxf.xscale < 0 < ins.dxf.yscale                           # mirrored in the DXF too


def test_dxf_text_height_is_the_capital_height_of_the_editor_font():
    from nova_legend.legend.export import CAP_HEIGHT, build_dxf

    doc = normalize({"version": 4, "blocks": [block("A", 1, "Taster")]})
    lay = layout(doc)
    dxf = build_dxf(lay, None, lambda prim: None)
    taster = next(t for t in dxf.modelspace().query("TEXT") if t.dxf.text == "Taster")
    assert abs(taster.dxf.height - 2.5 * CAP_HEIGHT) < 1e-3


def test_several_named_legends_per_project(env, monkeypatch):  # noqa: F811
    import sqlite3

    client, tmp = env
    pid = _project(client, tmp)
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    client.put(f"/api/projects/{pid}/legend", json={"doc": doc})
    first = client.get(f"/api/projects/{pid}/legends").json()["items"]
    assert [l["name"] for l in first] == ["Legende"]
    cat = doc["blocks"][0]["category_id"]
    made = client.post(f"/api/projects/{pid}/legends",
                       json={"name": "Brandmelder", "source": "proposal", "categories": [cat]}).json()
    bma = made["legend"]
    assert [l["name"] for l in made["items"]] == ["Legende", "Brandmelder"]
    assert {b["category_id"] for b in bma["doc"]["blocks"]} == {cat} and bma["doc"]["title"]["text"] == "Brandmelder"
    # each legend saves on its own; the first one stays where older versions read it
    bdoc = bma["doc"]
    bdoc["title"]["text"] = "BMA geändert"
    client.put(f"/api/projects/{pid}/legend", params={"legend": bma["id"]}, json={"doc": bdoc})
    assert client.get(f"/api/projects/{pid}/legend", params={"legend": bma["id"]}).json()["legend"]["doc"]["title"]["text"] == "BMA geändert"
    assert client.get(f"/api/projects/{pid}/legend").json()["legend"]["doc"]["title"]["text"] == doc["title"]["text"]
    folder = client.get(f"/api/projects/{pid}").json()["folder"]
    with sqlite3.connect(f"{folder}/projekt.nlproj") as con:
        old = con.execute("SELECT doc FROM legend WHERE id=1").fetchone()[0]
    assert doc["title"]["text"] in old
    # export names use the legend name when there are several
    name = client.get(f"/api/projects/{pid}/legend/export-name", params={"legend": bma["id"]}).json()["name"]
    assert name == "edeco ag-Test-Brandmelder.dxf"
    res = client.get(f"/api/projects/{pid}/legend/export/{name}", params={"legend": bma["id"], "general": "false"})
    assert res.status_code == 200
    # copy, rename, delete; the last legend stays
    copy = client.post(f"/api/projects/{pid}/legends", json={"name": "Kopie", "source": "copy",
                                                            "copy_of": bma["id"]}).json()["legend"]
    assert copy["doc"]["title"]["text"] == "BMA geändert"
    client.put(f"/api/projects/{pid}/legends/{copy['id']}", json={"name": "BMA Variante"})
    items = client.get(f"/api/projects/{pid}/legends").json()["items"]
    assert [l["name"] for l in items] == ["Legende", "Brandmelder", "BMA Variante"]
    for item in items[1:]:
        assert client.delete(f"/api/projects/{pid}/legends/{item['id']}").status_code == 200
    assert client.delete(f"/api/projects/{pid}/legends/{items[0]['id']}").status_code == 400
    assert client.get(f"/api/projects/{pid}/legend", params={"legend": 999}).status_code == 404


def test_template_hands_over_all_its_legends(env):  # noqa: F811
    client, tmp = env
    tpl = _project(client, tmp, "Vorlage")
    doc = client.post(f"/api/projects/{tpl}/legend/propose").json()["doc"]
    client.put(f"/api/projects/{tpl}/legend", json={"doc": doc})
    client.post(f"/api/projects/{tpl}/legends", json={"name": "Brandmelder", "source": "empty"})
    new = client.post("/api/projects", json={"name": "Neu", "template": tpl}).json()["id"]
    assert [l["name"] for l in client.get(f"/api/projects/{new}/legends").json()["items"]] == ["Legende", "Brandmelder"]


def test_export_pdf_draws_the_legend_on_one_page(env, monkeypatch, tmp_path):  # noqa: F811
    import re
    import zlib

    client, tmp = env
    monkeypatch.setattr(config, "current_user", lambda: "chef")
    client.put("/api/company/legend", json={"general_path": str(_template_dxf(tmp_path / "a.dxf"))})
    pid = _project(client, tmp)
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    doc = client.put(f"/api/projects/{pid}/legend", json={"doc": doc}).json()["legend"]["doc"]
    name = client.get(f"/api/projects/{pid}/legend/export-name", params={"format": "pdf"}).json()["name"]
    assert name == "edeco ag-Test-Legende.pdf"
    for general in ("true", "false"):
        res = client.get(f"/api/projects/{pid}/legend/export/{name}", params={"format": "pdf", "general": general})
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        data = res.content
        assert data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF")
        assert data.count(b"/Type /Page ") == 1
        stream = re.search(rb"stream\n(.*)\nendstream", data, re.S).group(1)
        ops = zlib.decompress(stream).decode()
        # texts as outlines, frames and symbol lines: the page is not empty
        assert ops.count("f*") >= 10 and " S" in ops or "\nS" in ops
        # the section colour of the header bar is on the page
        header = doc["blocks"][0]["style"]["header"].lstrip("#")
        r, g, b = (int(header[i:i + 2], 16) / 255 for i in (0, 2, 4))
        assert f"{r:.3f} {g:.3f} {b:.3f} rg" in ops
