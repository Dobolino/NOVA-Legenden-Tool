"""Phase 3: compare two imports of the same floor. No Trimble files needed."""

from __future__ import annotations

import ezdxf
import pytest
from fastapi.testclient import TestClient

from nova_legend import config
from nova_legend.api.app import AppState, create_app
from nova_legend.projects.diff import diff_counts, tally, unchanged_count

from synthetic import make_nzp
from test_phase2 import V2_LONG, import_dxf, nova_like_dxf


def test_diff_counts_kinds():
    rows = diff_counts({"a": 2, "b": 1, "c": 0, "d": 3}, {"a": 2, "b": 0, "c": 4, "e": 1})
    by_key = {row["key"]: row for row in rows}
    assert set(by_key) == {"b", "c", "d", "e"}
    assert by_key["b"]["kind"] == "weg" and by_key["b"]["delta"] == -1
    assert by_key["c"]["kind"] == "neu" and by_key["c"]["after"] == 4
    assert by_key["d"]["kind"] == "weg" and by_key["d"]["before"] == 3
    assert by_key["e"]["kind"] == "neu"
    assert unchanged_count({"a": 2, "b": 1}, {"a": 2, "b": 0}) == 1
    assert tally(rows) == {"neu": 2, "weg": 2, "geaendert": 0}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_LEGENDEN_HOME", str(tmp_path / "home"))
    nzp = make_nzp(tmp_path / "v2.nzp", "Test.Elektroinstallationen.V2.CH", [
        ("10", "10-10", "Schalter, Schema 0, UP"),
        ("20", "20-10", "Schalter, Schema 0, AP"),
        ("230", "230-10", "Brandmelder, UP"),
        ("290", "290-99", "Funk-Gateway"),
    ])
    s = config.load_settings()
    s.dataset_paths = [str(nzp)]
    s.company_folder = str(tmp_path / "firma")
    s.projects_folder = str(tmp_path / "Legenden")
    config.save_settings(s)
    state = AppState()
    state.first_start()
    return TestClient(create_app(state, ui_dir=tmp_path / "no-ui")), tmp_path


def test_first_import_has_nothing_to_compare(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    data = import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf")).json()
    assert data["plans"][0]["change_summary"] is None
    compared = client.get(f"/api/projects/{pid}/changes").json()["plans"][0]
    assert compared["comparable"] is False and compared["changes"] == []


def _revised(path):
    """Same switches, one more UP, no AP, no Brandmelder, no Gateway, two lines."""
    doc = ezdxf.new("R2013")
    doc.layers.add("E_Licht", color=5)
    doc.layers.add("E_Leitung_Licht", color=1)
    msp = doc.modelspace()

    def place(block, layer, attrs=None):
        blk = doc.blocks.new(block)
        blk.add_circle((0, 0), 125)
        ins = msp.add_blockref(block, (len(doc.blocks) * 1000, 0), dxfattribs={"layer": layer})
        for tag, value in (attrs or {}).items():
            ins.add_attrib(tag, value)

    origin = f"{V2_LONG} edeco AG"
    for n in range(4):
        place(f"Schalter_ Schema 0_ UP_A0TEST100{n}", "E_Licht",
              {"TypID": "10-10", "Bez": "Schalter, Schema 0, UP", "Herkunft": origin})
    place("Sensor_A0TEST1099", "E_Licht")
    place("Leitung_A0TEST1040", "E_Leitung_Licht")
    place("Leitung_A0TEST1041", "E_Leitung_Licht")
    doc.saveas(path)
    return path


def test_reimport_lists_new_gone_and_changed_counts(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    first = import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf"), "EG").json()
    plan_id = first["plans"][0]["id"]
    data = import_dxf(client, pid, _revised(tmp / "eg-neu.dxf"), plan_id=plan_id).json()
    summary = data["plans"][0]["change_summary"]
    assert summary == {"neu": 1, "weg": 3, "geaendert": 1}

    compared = client.get(f"/api/projects/{pid}/changes").json()["plans"][0]
    by_title = {}
    for row in compared["changes"]:
        by_title.setdefault(row["title"], []).append(row)
    switch = next(row for row in by_title["Schalter, Schema 0"] if row["item"] == "10-10")
    assert switch["kind"] == "geaendert" and switch["before"] == 3 and switch["after"] == 4 and switch["delta"] == 1
    assert next(row for row in by_title["Schalter, Schema 0"] if row["item"] == "20-10")["kind"] == "weg"
    assert by_title["Brandmelder"][0]["kind"] == "weg"
    assert by_title["Gateway"][0]["kind"] == "weg"
    sensor = next(row for row in compared["changes"] if row["name"] == "Sensor")
    assert sensor["kind"] == "neu" and sensor["status"] == "unbekannt"
    ignored = {row["name"]: row for row in compared["ignored_changes"]}
    assert ignored["Leitung"]["kind"] == "geaendert" and ignored["Leitung"]["before"] == 1 and ignored["Leitung"]["after"] == 2
    assert ignored["Plankopf edeco18"]["kind"] == "weg" and ignored["Plankopf edeco18"]["reason"] == "Plankopf"

    versions = compared["versions"]
    flipped = client.get(
        f"/api/projects/{pid}/plans/{plan_id}/changes",
        params={"older": versions[0]["id"], "newer": versions[1]["id"]},
    ).json()["plan"]
    switch = next(row for row in flipped["changes"] if row["item"] == "10-10")
    assert switch["before"] == 4 and switch["after"] == 3 and switch["delta"] == -1
    assert client.get(
        f"/api/projects/{pid}/plans/{plan_id}/changes", params={"older": 999, "newer": versions[0]["id"]}
    ).status_code == 400


def test_identical_reimport_reports_no_change(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    dxf = nova_like_dxf(tmp / "eg.dxf")
    data = import_dxf(client, pid, dxf, "EG").json()
    plan_id = data["plans"][0]["id"]
    data = import_dxf(client, pid, dxf, plan_id=plan_id).json()
    assert data["plans"][0]["versions"] == 2
    assert data["plans"][0]["change_summary"] == {"neu": 0, "weg": 0, "geaendert": 0}
    compared = client.get(f"/api/projects/{pid}/changes").json()["plans"][0]
    assert compared["changes"] == [] and compared["ignored_changes"] == [] and compared["unchanged"] >= 3


def test_merge_keeps_same_key_when_a_second_graphic_appears():
    from nova_legend.importer.model import Found
    from nova_legend.projects.store import merge_found

    previous = [{"source_key": "code:D|C1|G1", "name": "A", "count": 1, "item": "C1", "graphic_name": "G1"}]
    rows = merge_found(previous, [Found("code:D|C1|G2", "B", 2, item="C1", graphic_name="G2"),
                                  Found("code:D|C1|G1", "A", 3, item="C1", graphic_name="G1")])
    counts = {row["source_key"]: row["count"] for row in rows}
    assert counts == {"code:D|C1|G1": 3, "code:D|C1|G2": 2}


def test_merge_does_not_guess_between_datasets_with_the_same_code():
    from nova_legend.importer.model import Found
    from nova_legend.projects.store import merge_found

    previous = [{"source_key": "n4d:V1|90|90-30|2D-10", "name": "V1", "count": 4, "item": "90-30", "graphic_name": "G1"},
                {"source_key": "n4d:V2|90|90-30|2D-10", "name": "V2", "count": 5, "item": "90-30", "graphic_name": "G2"}]
    rows = merge_found(previous, [Found("code:X|90-30|G3", "Neu", 6, item="90-30", graphic_name="G3")])
    counts = {row["source_key"]: row["count"] for row in rows}
    assert counts == {"code:X|90-30|G3": 6, "n4d:V1|90|90-30|2D-10": 0, "n4d:V2|90|90-30|2D-10": 0}


def test_new_plan_version_without_floor_name_as_sent_by_the_ui(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    plan_id = import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf")).json()["plans"][0]["id"]
    res = import_dxf(client, pid, _revised(tmp / "eg-neu.dxf"), name="", plan_id=plan_id)
    assert res.status_code == 200, res.text
    assert res.json()["plans"][0]["versions"] == 2
    assert import_dxf(client, pid, nova_like_dxf(tmp / "x.dxf"), name="").status_code == 200  # name from file


def test_category_colour_check_merge_and_company_assignment(env):
    client = env[0]
    cats = client.get("/api/categories").json()["items"]
    general = next(c for c in cats if c["id"] == "allgemein")
    assert general["color"] == "#808080"           # «Allgemein» is grey by default
    first = next(c for c in cats if c["id"] != "allgemein")
    r = client.put(f"/api/categories/{first['id']}/color", json={"color": "#12AB34"})
    assert next(c for c in r.json()["items"] if c["id"] == first["id"])["color"] == "#12ab34"
    assert client.put(f"/api/categories/{first['id']}/color", json={"color": "rot"}).status_code == 400
    r = client.put("/api/categories/allgemein/color", json={"color": ""})
    assert next(c for c in r.json()["items"] if c["id"] == "allgemein")["color"] == ""

    a = client.post("/api/categories", json={"title": "Doppelt"}).json()
    b = client.post("/api/categories", json={"title": "doppelt"}).json()
    client.put(f"/api/categories/{a['id']}", json={"sheets": ["777"]})
    sub = client.post("/api/categories", json={"title": "Unter", "parent": b["id"]}).json()
    client.put("/api/category-family", json={"family_key": "fam-x", "categories": [b["id"], a["id"]]})
    hints = client.get("/api/categories/check").json()["items"]
    assert any(h["kind"] == "title" and set(h["ids"]) == {a["id"], b["id"]} for h in hints)

    r = client.post("/api/categories/merge", json={"source": b["id"], "target": a["id"]})
    items = {c["id"]: c for c in r.json()["items"]}
    assert b["id"] not in items and items[sub["id"]]["parent"] == a["id"]
    assert client.get("/api/category-family", params={"family_key": "fam-x"}).json()["categories"] == [a["id"]]
    assert client.post("/api/categories/merge", json={"source": a["id"], "target": a["id"]}).status_code == 400
