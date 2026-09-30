"""Phase 4: legend document, proposal, arrangement and the editor routes."""

from __future__ import annotations

from nova_legend.legend.model import AP_NOTE, auto_layout, empty_doc, fit_scale, normalize, propose
from nova_legend.render.engine import engine_geometry
from nova_legend.render.svg import geometry_bounds

from test_phase2 import import_dxf, nova_like_dxf
from test_phase3 import env  # noqa: F401 - fixture

CATS = [{"id": "allgemein", "title": "Allgemein", "columns": 2, "spacing": 4.55},
        {"id": "schalter", "title": "Schalter und Taster", "columns": 2, "spacing": 5.0},
        {"id": "versteckt", "title": "Versteckt", "hidden": True}]


def row(key, cats, total=2, mountings=None):
    return {"family_key": key, "symbol_key": f"sym:{key}", "title": key.title(), "categories": cats,
            "total": total, "mountings": mountings or {"UP": total}}


def test_proposal_groups_by_first_visible_category_and_skips_unused():
    rows = [row("schalter", ["schalter"]), row("dose", ["allgemein", "schalter"]),
            row("weg", ["schalter"], total=0), row("geheim", ["versteckt"]), row("frei", [])]
    doc = propose(rows, CATS, True, {"dose": "UP-Abzweigdose Decke / Wand"}, "Legende 1424")
    titles = [b["title"] for b in doc["blocks"]]
    assert titles == ["Allgemein", "Schalter und Taster", "Ohne Kategorie"]
    allgemein = doc["blocks"][0]["items"]
    assert [i["text"] for i in allgemein] == ["UP-Abzweigdose Decke / Wand"]   # company text wins
    assert doc["blocks"][1]["items"][0]["text"] == "Schalter" and doc["blocks"][1]["spacing"] == 5.0
    keys = {i["family_key"] for b in doc["blocks"] for i in b["items"]}
    assert "weg" not in keys and "geheim" not in keys


def test_proposal_without_categories_and_ap_note():
    rows = [row("schalter", ["schalter"], mountings={"UP": 1, "AP": 1}), row("dose", ["allgemein"])]
    doc = propose(rows, CATS, False, {}, "Legende")
    assert len(doc["blocks"]) == 1 and doc["blocks"][0]["title"] == ""
    notes = [i for i in doc["blocks"][0]["items"] if i["kind"] == "note"]
    assert [n["text"] for n in notes] == [AP_NOTE]


def test_auto_layout_rows_columns_and_page_flow():
    doc = empty_doc("T")
    doc["style"]["page_height"] = 60
    for n in range(3):
        doc["blocks"].append({"id": f"b{n}", "category_id": None, "title": f"B{n}", "x": 0, "y": 0,
                              "columns": 2 if n == 0 else 1, "spacing": 4.55, "heading_size": 3.5,
                              "collapsed": False,
                              "items": [{"id": f"i{n}{k}", "kind": "note", "text": "x", "x": 0, "y": 0}
                                        for k in range(6)]})
    out = auto_layout(normalize(doc))
    b0, b1, b2 = out["blocks"]
    ys = sorted({i["y"] for i in b0["items"]})
    assert len(ys) == 3 and round(ys[1] - ys[0], 2) == 4.55           # 6 entries in 2 columns
    assert len({i["x"] for i in b0["items"]}) == 2
    assert b1["x"] > b0["x"] or b1["y"] > b0["y"]
    columns = {b["x"] for b in out["blocks"]}
    assert len(columns) >= 2, "blocks flow into the next legend column"
    for a, b in [(b0, b1), (b1, b2)]:
        if a["x"] == b["x"]:
            assert b["y"] >= a["y"] + 3.5 * 1.8 + 3 * 4.55 - 0.01    # no overlap in one column


def test_normalize_cleans_client_data():
    doc = normalize({"style": {"grid": "x", "page_columns": 99}, "title": {"text": "L"},
                     "blocks": [{"id": "a", "columns": 0, "items": [
                         {"id": "same", "kind": "symbol"},                           # no symbol: dropped
                         {"id": "same", "kind": "symbol", "symbol_key": "k", "scale": 500},
                         {"id": "same", "kind": "line", "line_style": "wavy"}]}],
                     "texts": [{"text": "  "}, {"text": "Hinweis", "x": 3}]})
    items = doc["blocks"][0]["items"]
    assert len(items) == 2 and items[0]["id"] != items[1]["id"]
    assert items[0]["scale"] == 20 and items[1]["line_style"] == "solid"
    assert doc["blocks"][0]["columns"] == 1 and doc["style"]["page_columns"] == 8
    assert doc["style"]["grid"] == 0.5 and [t["text"] for t in doc["texts"]] == ["Hinweis"]


def test_luminaire_length_changes_the_drawing():
    content = "2DNeutral;Typ=0;A=*L;B=*;A1=0;B1=0;Lines=3"
    short = geometry_bounds(engine_geometry(content, {"L": "600", "B": "600"}))
    long = geometry_bounds(engine_geometry(content, {"L": "1500", "B": "300"}))
    assert round((long[2] - long[0]) / (short[2] - short[0]), 2) == 2.5
    assert round((long[3] - long[1]) / (short[3] - short[1]), 2) == 0.5


def test_legend_routes_roundtrip(env):  # noqa: F811
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test", "project_number": "1424"}).json()["id"]
    empty = client.get(f"/api/projects/{pid}/legend").json()
    assert empty["legend"] is None and "Lichtinstallation" in empty["template_texts"]
    import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf"))
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    assert doc["title"]["text"] == "Legende 1424 Test"
    items = [i for b in doc["blocks"] for i in b["items"] if i["kind"] == "symbol"]
    assert items and all(i["symbol_key"] for i in items)
    doc["blocks"][0]["items"][0]["text"] = "Eigener Text"
    saved = client.put(f"/api/projects/{pid}/legend", json={"doc": doc}).json()["legend"]
    assert saved["updated_by"] and saved["doc"]["blocks"][0]["items"][0]["text"] == "Eigener Text"
    again = client.get(f"/api/projects/{pid}/legend").json()["legend"]["doc"]
    assert again == saved["doc"]
    svgs = client.post("/api/legend/symbols", json={"items": [
        {"symbol_key": items[0]["symbol_key"], "family_key": items[0]["family_key"]}]}).json()["items"]
    first = svgs[0]
    assert first["svg"].startswith("<svg") and len(first["box"]) == 4
    laid = client.post("/api/legend/layout", json={"doc": saved["doc"]}).json()["doc"]
    assert laid["blocks"][0]["y"] > laid["title"]["y"]


def test_company_description_is_used_for_new_proposals(env):  # noqa: F811
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf"))
    fam = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]["blocks"][0]["items"][0]["family_key"]
    assert client.put("/api/descriptions", json={"family_key": fam, "text": "Firmentext A"}).json()["text"] == "Firmentext A"
    texts = [i["text"] for b in client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]["blocks"]
             for i in b["items"]]
    assert "Firmentext A" in texts
    sug = client.get("/api/legend/texts", params={"q": "Brandmelder", "family_key": fam}).json()["items"]
    assert sug[0] == {"text": "Firmentext A", "score": 100, "source": "Firmentext"}
    assert any(s["text"] == "Brandmelder / Indikator" for s in sug)
    client.put("/api/descriptions", json={"family_key": fam, "text": ""})
    assert client.get("/api/legend/texts", params={"family_key": fam}).json()["items"] == []


def test_large_symbols_are_shrunk_to_the_row_small_ones_stay():
    assert fit_scale(5, 5, 4.55, 9.75) == 1.0
    assert fit_scale(12, 12, 4.55, 9.75) == 0.4          # 5.0 / 12 -> 0.41 -> 0.40
    assert fit_scale(30, 3, 4.55, 9.75) == 0.55          # width limit 16.5 / 30
    rows = [row("pfeil", ["schalter"])]
    doc = propose(rows, CATS, True, {}, "L", size_of=lambda key: (20.0, 10.0))
    assert doc["blocks"][0]["items"][0]["scale"] == 0.55  # 5.5 / 10
