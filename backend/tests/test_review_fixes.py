"""Regression tests for the review findings of October 2026."""

from __future__ import annotations

from nova_legend.library.store import Library

from synthetic import make_nzp


def test_missing_dataset_file_keeps_its_cached_symbols(tmp_path):
    item = [("10", "10-10", "Schalter, UP")]
    nzp = make_nzp(tmp_path / "a.nzp", "Test.Elo", item)
    lib = Library(tmp_path / "lib.sqlite")
    assert lib.sync([str(nzp)])["neu"] == ["Test.Elo"]
    count = len(lib.symbols())
    offline = nzp.rename(tmp_path / "a.offline")            # network drive away
    report = lib.sync([str(nzp)])
    assert report["entfernt"] == [] and len(lib.symbols()) == count
    assert "bleiben erhalten" in report["fehler"][0]
    nzp.write_bytes(b"broken")                               # half copied file
    report = lib.sync([str(nzp)])
    assert report["entfernt"] == [] and len(lib.symbols()) == count
    nzp.unlink()
    offline.rename(nzp)
    assert lib.sync([str(nzp)])["fehler"] == []
    assert lib.sync([])["entfernt"] == ["Test.Elo"]          # removed from the list: gone
    assert lib.symbols() == []


def test_dxf_multiple_insert_counts_every_apparatus(tmp_path):
    import ezdxf

    from nova_legend.importer.dxf import read_dxf

    doc = ezdxf.new("R2013")
    doc.layers.add("E_Licht")
    doc.blocks.new("Brandmelder_ UP_A0TEST0020").add_circle((0, 0), 125)
    msp = doc.modelspace()
    ins = msp.add_blockref("Brandmelder_ UP_A0TEST0020", (0, 0), dxfattribs={"layer": "E_Licht"})
    ins.dxf.row_count, ins.dxf.column_count = 2, 3            # MINSERT: 2 x 3 = six apparatus
    ins.dxf.row_spacing, ins.dxf.column_spacing = 1000, 1000
    msp.add_blockref("Brandmelder_ UP_A0TEST0020", (9000, 0), dxfattribs={"layer": "E_Licht"})
    doc.saveas(tmp_path / "m.dxf")
    found = read_dxf(tmp_path / "m.dxf").found
    assert [(f.name, f.count, f.layers) for f in found] == [("Brandmelder, UP", 7, {"E_Licht": 7})]


def test_project_names_with_a_leading_underscore_stay_visible(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_LEGENDEN_HOME", str(tmp_path / "home"))
    from nova_legend.projects.store import ProjectManager

    store = ProjectManager(tmp_path / "Legenden")
    store.ensure_root()
    p = store.create("_Umbau Nord", "19.2")
    assert p.folder.name == "Umbau Nord" and p.meta()["name"] == "_Umbau Nord"
    assert [i["name"] for i in store.list()] == ["_Umbau Nord"]
    q = store.create("_", "19.2")
    assert q.folder.name == "Projekt"
    r = store.rename(q.id, ".versteckt")
    assert r.folder.name == "versteckt" and len(store.list()) == 2


def test_named_source_dataset_is_never_replaced_by_another_catalogue():
    from types import SimpleNamespace as S

    from nova_legend.importer.model import Found
    from nova_legend.importer.recognize import LibraryIndex, resolve

    def sym(ds, item, name):
        return S(key=f"{ds}|{item}", dataset=ds, item=item, name=name, part_name="", sheet="90", graphic_id="")

    v1, v2 = "Trimble.Elektroinstallationen.CH", "Trimble.Elektroinstallationen.V2.CH"
    index = LibraryIndex([sym(v2, "90-30", "Steckdose T13"), sym(v1, "90-10", "Steckdose T13 alt")],
                         [{"id": v1, "long_name": "Elektro"}, {"id": v2, "long_name": "Elektro V2"}])
    # code only in the other catalogue: unknown, not "erkannt"
    r = resolve(Found("k1", "Steckdose T13", dataset=v1, item="90-30"), index, {})
    assert (r.status, r.symbol_key) == ("unbekannt", None)
    # dataset not in the library at all: no guess either
    r = resolve(Found("k2", "Steckdose T13", dataset="Fremd.Katalog", item="90-30"), index, {})
    assert r.status == "unbekannt"
    # right dataset: recognised
    assert resolve(Found("k3", "x", dataset=v2, item="90-30"), index, {}).symbol_key == f"{v2}|90-30"
    # no dataset given (DXF without attributes): name and newest catalogue as before
    assert resolve(Found("k4", "Steckdose T13"), index, {}).status == "erkannt"
    # the user's decision still wins
    assert resolve(Found("k1", "Steckdose T13", dataset=v1, item="90-30"), index,
                   {"k1": f"{v2}|90-30"}).status == "zugeordnet"


def test_objects_without_graphic_are_only_ignored_for_catalogues_without_symbols():
    from types import SimpleNamespace as S

    from nova_legend.importer.model import Found
    from nova_legend.importer.recognize import LibraryIndex, resolve

    elo = "Trimble.Elektroinstallationen.CH"
    index = LibraryIndex([S(key=f"{elo}|10|10-10|2D-10", dataset=elo, item="10-10", name="Schalter",
                            part_name="", sheet="10", graphic_id="2D-10")],
                         [{"id": elo, "long_name": "Elektro"}, {"id": "Plancal.EloTrassen", "long_name": "Trassen"}])
    lamp = Found("n4d:x", "Spezialleuchte", 5, elo, "999-1", "999", features={"has_graphic": False})
    tray = Found("n4d:y", "Kabelkanal", 19, "Plancal.EloTrassen", "Kabelkanal", "Tra1",
                 features={"has_graphic": False})
    assert (resolve(lamp, index, {}).status, resolve(lamp, index, {}).method) == ("unbekannt", "ohne Grafik")
    assert resolve(tray, index, {}).status == "ignoriert"


def test_linear_luminaires_get_the_sheet_graphic_sized_by_the_part(tmp_path):
    from nova_legend.render.engine import engine_geometry
    from nova_legend.render.svg import geometry_bounds

    content = "Langfeldleuchte;L=*;B=*;H=*;AnzR=*Ctx1;Abgependelt=False; MitSicherheitsleuchte=False; DArt=0 ;GZusatz=UNDEF"
    geo = engine_geometry(content, {"L": "800", "B": "80", "Ctx1": "2"})
    x0, y0, x1, y1 = geometry_bounds(geo)
    assert round((x1 - x0) * 1000, 2) == 16.0 and round((y1 - y0) * 1000, 2) == 1.6     # 800 x 80 mm at 1:50
    assert sum(1 for p in geo.primitives if p.kind == "line") == 2                       # one line per tube
    safety = engine_geometry(content.replace("MitSicherheitsleuchte=False", "MitSicherheitsleuchte=True"),
                             {"L": "800", "B": "80"})
    assert any(p.filled for p in safety.primitives)
