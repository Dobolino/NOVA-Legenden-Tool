"""Phase 2: projects, plan import, recognition, mappings (no Trimble files needed).

Real-file checks at the end are skipped when the samples are missing.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.parse import unquote

import ezdxf
import pytest
from fastapi.testclient import TestClient

from nova_legend import config
from nova_legend.api.app import AppState, create_app
from nova_legend.importer.dxf import display_name, read_dxf
from nova_legend.importer.model import Found
from nova_legend.importer.n4d import n4d_layer_colors
from nova_legend.matcher.suggest import suggest
from nova_legend.projects.colors import pick_category_layer
from nova_legend.projects.floors import floor_name_from_filename, resolve_plan_name
from nova_legend.projects.store import ProjectManager, export_filename, safe_folder_name

from synthetic import make_nzp

V2 = "Test.Elektroinstallationen.V2.CH"
V2_LONG = f"{V2} Test"            # LongName written by make_nzp
SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def nova_like_dxf(path: Path) -> Path:
    """A small plan like a Nova DXF export: one block per placement."""
    doc = ezdxf.new("R2013")
    doc.layers.add("E_Licht", color=5)
    doc.layers.add("E_Leitung_Licht", color=1)
    msp = doc.modelspace()

    def place(block: str, layer: str, attrs: dict[str, str] | None = None, circles: int = 1):
        blk = doc.blocks.new(block)
        for i in range(circles):
            blk.add_circle((0, 0), 125 + i * 10)
        ins = msp.add_blockref(block, (len(doc.blocks) * 1000, 0), dxfattribs={"layer": layer})
        for tag, value in (attrs or {}).items():
            ins.add_attrib(tag, value)

    for n in range(3):   # three UP switches with attributes
        place(f"Schalter_ Schema 0_ UP_A0TEST000{n}", "E_Licht",
              {"TypID": "10-10", "Bez": "Schalter, Schema 0, UP", "Herkunft": f"{V2_LONG} edeco AG"})
    place("Schalter_ Schema 0_ AP_A0TEST0010", "E_Licht",
          {"TypID": "20-10", "Bez": "Schalter, Schema 0, AP", "Herkunft": f"{V2_LONG} edeco AG"})
    place("Brandmelder_ UP_A0TEST0020", "E_Licht")                    # no attributes, name known
    place("Gateway_A0TEST0030", "E_Licht", circles=2)                  # unknown
    place("Leitung_A0TEST0040", "E_Leitung_Licht")                     # never apparatus
    place("Plankopf edeco18", "0")                                     # frame, not apparatus
    doc.saveas(path)
    return path


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_LEGENDEN_HOME", str(tmp_path / "home"))
    nzp = make_nzp(tmp_path / "v2.nzp", V2, [
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
    client = TestClient(create_app(state, ui_dir=tmp_path / "no-ui"))
    return client, tmp_path


def import_dxf(client, pid: str, dxf: Path, name: str = "EG", plan_id: int | None = None):
    data = {"name": name}
    if plan_id:
        data["plan_id"] = str(plan_id)
    with open(dxf, "rb") as fh:
        return client.post(f"/api/projects/{pid}/plans", data=data, files={"file": (dxf.name, fh)})


# -- DXF reader -----------------------------------------------------------------

def test_read_dxf_finds_apparatus_and_skips_lines(tmp_path):
    result = read_dxf(nova_like_dxf(tmp_path / "plan.dxf"))
    by_name = {f.name: f for f in result.found}
    assert by_name["Schalter, Schema 0, UP"].count == 3
    assert by_name["Schalter, Schema 0, UP"].item == "10-10"
    assert "Brandmelder, UP" in by_name and "Gateway" in by_name
    assert result.ignored == {"Leitung": 1, "Plankopf edeco18": 1}
    colors = {l.name: l.color for l in result.layers}
    assert colors["E_Licht"] == "#0000ff" and colors["E_Leitung_Licht"] == "#ff0000"
    assert by_name["Gateway"].features["arc"] == 2


def test_display_name():
    assert display_name("Steckdose T13_ UP_ 3-fach") == "Steckdose T13, UP, 3-fach"


def test_n4d_layer_colour_pattern():
    name = "E_Licht".encode("utf-16le")
    data = b"\x00" + b"\xff\xfe\xff" + bytes([7]) + name + bytes([0, 128, 255, 0, 0, 128, 255, 0]) + b"\x01"
    assert n4d_layer_colors(data) == {"E_Licht": "#0080ff"}


# -- project store ------------------------------------------------------------------

def test_project_manager_lifecycle(tmp_path):
    m = ProjectManager(tmp_path / "Legenden")
    p = m.create("Haus A: Umbau", "19.2")
    assert p.folder.name == safe_folder_name("Haus A: Umbau") == "Haus A_ Umbau"
    p.set_settings({"legend_columns": 2})
    t = m.create("Haus B", "20", template=p.id)
    assert t.settings() == {"legend_columns": 2} and t.meta()["template_from"] == p.id
    c = m.copy(p.id, "Haus A Kopie")
    assert c.meta()["name"] == "Haus A Kopie"
    r = m.rename(c.id, "Haus C")
    assert r.folder.name == "Haus C" and r.meta()["name"] == "Haus C"
    moved = m.delete(t.id)
    assert moved.parent.name == "_Geloescht"
    assert sorted(x["name"] for x in m.list()) == ["Haus A: Umbau", "Haus C"]
    with pytest.raises(ValueError):
        m.create("  ", "19.2")
    with pytest.raises(KeyError):
        m.get("../etwas")


# -- API: import, overall list, unknown, mappings ----------------------------------------

def test_import_and_overall_list(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test", "nova_version": "19.2"}).json()["id"]
    res = import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf"), "EG")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["stats"] == {"erkannt": 5, "unbekannt": 1}
    rows = {r["title"]: r for r in data["rows"]}
    plan_id = str(data["plans"][0]["id"])
    switch = rows["Schalter, Schema 0"]
    assert switch["counts"][plan_id] == 4                       # UP and AP in one family
    assert switch["mountings"] == {"UP": 3, "AP": 1}
    assert rows["Brandmelder"]["counts"][plan_id] == 1
    assert [u["name"] for u in data["unknown"]] == ["Gateway"]
    assert {l["name"] for l in data["layers"]} >= {"E_Licht", "E_Leitung_Licht"}


def test_second_plan_gives_second_column_and_reimport_adds_version(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    dxf = nova_like_dxf(tmp / "plan.dxf")
    import_dxf(client, pid, dxf, "EG")
    data = import_dxf(client, pid, dxf, "1. OG").json()
    assert [p["name"] for p in data["plans"]] == ["EG", "1. OG"]
    switch = next(r for r in data["rows"] if r["title"] == "Schalter, Schema 0")
    assert switch["total"] == 8 and len(switch["counts"]) == 2
    first = data["plans"][0]["id"]
    data = import_dxf(client, pid, dxf, plan_id=first).json()
    assert data["plans"][0]["versions"] == 2
    versions = client.get(f"/api/projects/{pid}/plans/{first}/versions").json()["items"]
    assert len(versions) == 2


def test_unknown_suggestions_and_mapping(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    data = import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf")).json()
    key = data["unknown"][0]["source_key"]
    sug = client.get(f"/api/projects/{pid}/suggestions", params={"source_key": key}).json()["items"]
    assert sug[0]["name"] == "Funk-Gateway" and sug[0]["score"] > 50
    assert client.put("/api/mappings", json={"source_key": key, "symbol_key": "nope"}).status_code == 400
    client.put("/api/mappings", json={"source_key": key, "symbol_key": sug[0]["symbol_key"]})
    data = client.get(f"/api/projects/{pid}").json()
    assert data["unknown"] == [] and any(r["title"] == "Funk-Gateway" for r in data["rows"])
    # the decision applies to the next import automatically
    pid2 = client.post("/api/projects", json={"name": "Anderes"}).json()["id"]
    data2 = import_dxf(client, pid2, nova_like_dxf(tmp / "og.dxf")).json()
    assert data2["unknown"] == []
    # ignore instead
    client.put("/api/mappings", json={"source_key": key, "symbol_key": "__ignore__"})
    data3 = client.get(f"/api/projects/{pid}").json()
    assert data3["stats"]["ignoriert"] == 1 and data3["ignored"][0]["manual"]


def test_import_rejects_other_files(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    bad = tmp / "notiz.txt"
    bad.write_text("x")
    with open(bad, "rb") as fh:
        res = client.post(f"/api/projects/{pid}/plans", data={"name": "EG"}, files={"file": ("notiz.txt", fh)})
    assert res.status_code == 400
    broken = tmp / "kaputt.dxf"
    broken.write_text("kein dxf")
    assert import_dxf(client, pid, broken).status_code == 400
    dwg = tmp / "plan.dwg"
    dwg.write_bytes(b"AC1027")
    res = import_dxf(client, pid, dwg)
    assert res.status_code == 400 and "ODA" in res.json()["detail"]


def test_project_api_copy_template_export_delete(env):
    client, _tmp = env
    pid = client.post("/api/projects", json={"name": "Vorlage", "nova_version": "20"}).json()["id"]
    new = client.post("/api/projects", json={"name": "Neu", "template": pid}).json()
    assert new["meta"]["template_from"] == pid
    assert client.post("/api/projects", json={"name": "X", "template": "gibt-es-nicht"}).status_code == 400
    renamed = client.put(f"/api/projects/{new['id']}", json={"name": "Neu 2", "nova_version": "19.2"}).json()
    assert renamed["meta"]["name"] == "Neu 2" and renamed["meta"]["nova_version"] == "19.2"
    exported = client.get(f"/api/projects/{pid}/export")
    assert "edeco ag-Vorlage-projekt.zip" in unquote(exported.headers["content-disposition"])
    zip_bytes = exported.content
    assert any(n.endswith("projekt.nlproj") for n in zipfile.ZipFile(io.BytesIO(zip_bytes)).namelist())
    assert client.delete(f"/api/projects/{pid}").json()["ok"]
    assert [p["name"] for p in client.get("/api/projects").json()["items"]] == ["Neu 2"]


def test_floor_names_and_export_filename():
    assert floor_name_from_filename("3_1.OG.dxf") == "1. OG"
    assert floor_name_from_filename("EG.dxf") == "EG"
    assert floor_name_from_filename("1. OG.n4d") == "1. OG"
    assert floor_name_from_filename("2.Stock.dxf") == "2. Stock"
    assert floor_name_from_filename("plan_EG_1.OG.dxf") == "1. OG"
    assert floor_name_from_filename("Lageplan.dxf") is None
    assert resolve_plan_name("3_1.OG.dxf", "") == "1. OG"
    assert resolve_plan_name("3_1.OG.dxf", "3_1.OG") == "1. OG"
    assert resolve_plan_name("3_1.OG.dxf", "Keller") == "Keller"
    assert export_filename({"name": "Vorlage"}) == "edeco ag-Vorlage-projekt.zip"


def test_category_layer_matches_tail_not_a_different_light_layer():
    layers = [
        {"name": "E_232.5_Licht", "color": "#0080ff"},
        {"name": "E_Leitung_Licht", "color": "#ff0000"},
        {"name": "E_233_Leuchten", "color": "#00ff00"},
    ]
    picked = pick_category_layer("E_Licht", layers, {}, None)
    assert picked["layer"] == "E_232.5_Licht" and picked["color"] == "#0080ff" and not picked["manual"]
    both = layers + [{"name": "E_232_Licht", "color": "#111111"}]
    busier = pick_category_layer("E_Licht", both, {"E_232_Licht": 4, "E_232.5_Licht": 1}, None)
    assert busier["layer"] == "E_232_Licht"
    leitung = pick_category_layer("E_Leitung_Licht", layers, {}, None)
    assert leitung["layer"] == "E_Leitung_Licht"
    missing = pick_category_layer("E_Licht", [layers[2]], {}, None)
    assert missing["color"] == "" and "E_Licht" in missing["reason"]
    chosen = pick_category_layer("E_Licht", layers, {}, "E_233_Leuchten")
    assert chosen["manual"] and chosen["layer"] == "E_233_Leuchten" and chosen["color"] == "#00ff00"


def test_gruppenzuleitung_is_not_filtered(tmp_path):
    doc = ezdxf.new("R2013")
    doc.layers.add("E_Licht", color=5)
    blk = doc.blocks.new("Gruppenzuleitung_A0TEST0001")
    blk.add_circle((0, 0), 50)
    doc.modelspace().add_blockref(blk.name, (0, 0), dxfattribs={"layer": "E_Licht"})
    path = tmp_path / "g.dxf"
    doc.saveas(path)
    result = read_dxf(path)
    assert any(f.name == "Gruppenzuleitung" for f in result.found)
    assert "Gruppenzuleitung" not in result.ignored


def test_geometry_can_suggest_a_renamed_symbol():
    class Sym:
        def __init__(self, name, key):
            self.name = name
            self.key = key
            self.item = "1-1"
            self.dataset = "d"
            self.mounting = None
            self.svg = ""
            self.sheet = "1"

    symbols = [Sym(f"Xyzzqq Variante {i}", f"n{i}") for i in range(45)]
    symbols.append(Sym("Kreisding", "circle"))

    def feature_of(sym):
        return {"arc": 1} if sym.key == "circle" else {"line": 6}

    found = Found("name:xyzzqq", "Xyzzqq", features={"arc": 1})
    ranked = suggest(found, symbols, feature_of, {}, lambda _sym: [], limit=50)
    assert any(row["symbol_key"] == "circle" for row in ranked)


def test_filename_becomes_floor_name(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Haus", "project_number": "2026-1"}).json()["id"]
    path = nova_like_dxf(tmp / "3_1.OG.dxf")
    data = import_dxf(client, pid, path, name=path.stem).json()
    assert data["plans"][0]["name"] == "1. OG"
    assert data["meta"]["project_number"] == "2026-1"
    assert data["export_name"] == "edeco ag-Haus-projekt.zip"
    hidden = client.put(f"/api/projects/{pid}", json={"use_as_template": False}).json()
    assert hidden["meta"]["use_as_template"] is False
    listed = next(p for p in client.get("/api/projects").json()["items"] if p["id"] == pid)
    assert listed["use_as_template"] is False and listed["project_number"] == "2026-1"


def test_bkp_layer_colour_and_project_override(env):
    client, tmp = env
    doc = ezdxf.new("R2013")
    doc.layers.add("E_232.5_Licht", color=5)
    doc.layers.add("E_233_Leuchten", color=3)
    blk = doc.blocks.new("Schalter_A0TEST0001")
    blk.add_circle((0, 0), 125)
    ins = doc.modelspace().add_blockref(blk.name, (0, 0), dxfattribs={"layer": "E_232.5_Licht"})
    ins.add_attrib("TypID", "10-10")
    ins.add_attrib("Bez", "Schalter, Schema 0, UP")
    ins.add_attrib("Herkunft", f"{V2_LONG} edeco AG")
    path = tmp / "bkp.dxf"
    doc.saveas(path)
    pid = client.post("/api/projects", json={"name": "Farben"}).json()["id"]
    data = import_dxf(client, pid, path).json()
    licht = next(c for c in data["category_colors"] if c["id"] == "licht")
    assert licht["layer"] == "E_232.5_Licht" and licht["color"] == "#0000ff"
    leitung = next(c for c in data["category_colors"] if c["id"] == "leitungen")
    assert leitung["layer"] == "" and "E_Leitung_Licht" in leitung["reason"]
    changed = client.put(f"/api/projects/{pid}/category-layer",
                         json={"category_id": "licht", "layer": "E_233_Leuchten"}).json()
    licht = next(c for c in changed["category_colors"] if c["id"] == "licht")
    assert licht["manual"] and licht["color"] == "#00ff00"
    copy = client.post("/api/projects", json={"name": "Kopie Farbe", "template": pid}).json()
    again = next(c for c in copy["category_colors"] if c["id"] == "licht")
    assert again["manual"] and again["layer"] == "E_233_Leuchten"


def test_reimport_keeps_rows_and_one_file_then_detach(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    data = import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf"), "EG").json()
    plan_id = data["plans"][0]["id"]
    names = {g["name"]: g for g in data["ignored"]}
    assert names["Leitung"]["manual"] is False and names["Leitung"]["reason"] == "Leitung"
    assert names["Plankopf edeco18"]["reason"] == "Plankopf"
    switch_key = next(k for k in next(r["sources"] for r in data["rows"] if r["title"] == "Schalter, Schema 0")
                      if "10-10" in k)
    brand_key = next(r["sources"][0] for r in data["rows"] if r["title"] == "Brandmelder")

    doc = ezdxf.new("R2013")
    doc.layers.add("E_Licht", color=5)
    blk = doc.blocks.new("Schalter_ Schema 0_ UP_A0NEU00001")
    blk.add_circle((0, 0), 125)
    ins = doc.modelspace().add_blockref(blk.name, (0, 0), dxfattribs={"layer": "E_Licht"})
    ins.add_attrib("TypID", "10-10")
    ins.add_attrib("Bez", "Schalter, Schema 0, UP")
    ins.add_attrib("Herkunft", f"{V2_LONG} edeco AG Basel")   # same dataset, other company text
    second = tmp / "eg-neu.dxf"
    doc.saveas(second)
    data = import_dxf(client, pid, second, plan_id=plan_id).json()
    assert data["plans"][0]["versions"] == 2
    switch = next(r for r in data["rows"] if r["title"] == "Schalter, Schema 0")
    assert switch_key in switch["sources"] and switch["total"] == 1
    brand = next(r for r in data["rows"] if r["title"] == "Brandmelder")
    assert brand["total"] == 0 and brand_key in brand["sources"]
    stored = list((tmp / "Legenden" / pid / "Plaene").iterdir())
    assert len(stored) == 1 and stored[0].name.endswith("eg-neu.dxf")

    data = client.post(f"/api/projects/{pid}/plans/{plan_id}/detach").json()
    assert data["plans"][0]["file_name"] == ""
    assert next(r for r in data["rows"] if r["title"] == "Brandmelder")["total"] == 0
    assert list((tmp / "Legenden" / pid / "Plaene").iterdir()) == []
    data = client.post(f"/api/projects/{pid}/rows/delete", json={"source_keys": [brand_key]}).json()
    assert not any(r["title"] == "Brandmelder" for r in data["rows"])


# -- real files (skipped without samples) -----------------------------------------------------

@pytest.mark.skipif(not (SAMPLES / "3_1.OG.n4d").exists(), reason="samples missing")
def test_real_og_plan_counts():
    from nova_legend.importer.n4d import read_n4d
    n4d = read_n4d(SAMPLES / "3_1.OG.n4d")
    assert sum(f.count for f in n4d.found if f.features.get("has_graphic")) >= 230
    colors = {l.name: l.color for l in n4d.layers}
    assert colors["E_232.5_Licht"] == "#0080ff"
    dxf = read_dxf(SAMPLES / "3_1.OG.dxf")
    # 214 inserts carry TypID, one of them empty (the renamed distribution board)
    assert sum(f.count for f in dxf.found if f.item) == 213


def test_same_function_in_v1_and_v2_is_one_row(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_LEGENDEN_HOME", str(tmp_path / "home"))
    v2 = make_nzp(tmp_path / "v2.nzp", V2, [("10", "10-10", "Schalter, Schema 0, UP")])
    v1 = make_nzp(tmp_path / "v1.nzp", "Test.Elektroinstallationen.CH", [("10", "10-10", "Schalter, Schema 0, UP")])
    s = config.load_settings()
    s.dataset_paths = [str(v2), str(v1)]
    s.company_folder = str(tmp_path / "firma")
    s.projects_folder = str(tmp_path / "Legenden")
    config.save_settings(s)
    state = AppState()
    state.first_start()
    client = TestClient(create_app(state, ui_dir=tmp_path / "no-ui"))
    doc = ezdxf.new("R2013")
    msp = doc.modelspace()
    for n, origin in enumerate([V2_LONG, "Test.Elektroinstallationen.CH Test"]):
        blk = doc.blocks.new(f"Schalter_ Schema 0_ UP_A0TEST00{n}0")
        blk.add_circle((0, 0), 125)
        ins = msp.add_blockref(blk.name, (n * 1000, 0), dxfattribs={"layer": "E_Licht"})
        ins.add_attrib("TypID", "10-10")
        ins.add_attrib("Bez", "Schalter, Schema 0, UP")
        ins.add_attrib("Herkunft", f"{origin} edeco AG")
    doc.saveas(tmp_path / "mix.dxf")
    pid = client.post("/api/projects", json={"name": "Mix"}).json()["id"]
    data = import_dxf(client, pid, tmp_path / "mix.dxf").json()
    rows = [r for r in data["rows"] if r["title"] == "Schalter, Schema 0"]
    assert len(rows) == 1 and rows[0]["total"] == 2 and len(rows[0]["datasets"]) == 2
