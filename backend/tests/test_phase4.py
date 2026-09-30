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
    assert sch["style"]["header"] == "#0000ff" and sch["style"]["symbol"] == "#0000ff"
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
    assert doc["version"] == 2 and doc["style"]["text_size"] == 3.0 and doc["style"]["columns"] == 2
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


def test_sections_have_header_background_and_border_in_their_colours():
    doc = normalize({"blocks": [{"id": "k", "title": "Kraft", "style": section_style("#e03131"),
                                 "items": [{"id": "l", "kind": "line", "text": "AP-Leitung"}]}]})
    lay = layout(doc)
    roles = {p.get("role"): p for p in lay["prims"] if p["t"] == "rect"}
    assert roles["header"]["fill"] == "#e03131" and roles["border"]["stroke"] == "#e03131"
    assert roles["background"]["fill"] != "#ffffff"
    line = next(p for p in lay["prims"] if p["t"] == "line")
    assert line["color"] == "#e03131"
    doc["blocks"][0]["style"]["border_on"] = False
    assert "border" not in {p.get("role") for p in layout(doc)["prims"]}


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
