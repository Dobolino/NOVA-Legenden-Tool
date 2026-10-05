"""User stencils (Benutzerschablonen.n5q): reading, folder per Nova version, legend texts."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from nova_legend.parser.stencil import StencilEntry, stencil_folder

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "Benutzerschablonen.n5q"


def test_stencil_folder_follows_the_nova_version():
    template = r"%USERPROFILE%\OneDrive - edeco AG\Dokumente\Trimble\nova{nova}\Stencils"
    assert str(stencil_folder(template, "19.2", "C:/Users/aduerger")).endswith(r"Trimble\nova19\Stencils")
    assert r"\nova20\Stencils" in str(stencil_folder(template, "20", "C:/Users/aduerger"))
    assert str(stencil_folder(template, "20", "C:/Users/aduerger")).startswith("C:/Users/aduerger")


def test_entry_label_falls_back_to_the_object_name():
    assert StencilEntry("", object_name="Kontrolllampe Gr1, UP").label == "Kontrolllampe Gr1, UP"
    assert StencilEntry("Leerdose", object_name="x").label == "Leerdose"


@pytest.mark.skipif(not SAMPLE.exists(), reason="samples missing")
def test_reads_sets_tabs_and_entries_of_the_edeco_stencil():
    from nova_legend.parser.stencil import read_stencil_file

    sets = read_stencil_file(SAMPLE)
    assert [s.name for s in sets] == ["edeco", "edeco V2"]
    tabs = {t.name: t for t in sets[0].tabs}
    assert len(sets[0].tabs) == 21 and "Brandmeldeanlagen" in tabs and "Leuchten" in tabs
    entries = [e for s in sets for t in s.tabs for e in t.entries]
    assert len(entries) > 500 and all(e.label for e in entries)
    switch = next(e for e in tabs["Schalter / Taster"].entries if e.item == "10-70")
    assert switch.graphic_id == "2D-10" and switch.layer == "E_232.5_Licht"
    assert any(e.macro and e.macro.endswith("Plankopf edeco18.n4d") for e in tabs["Layout / Beschriftungen"].entries)


@pytest.mark.skipif(not SAMPLE.exists(), reason="samples missing")
def test_api_lists_the_stencil_and_proposals_use_its_names(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from nova_legend import config
    from nova_legend.api.app import AppState, create_app
    from synthetic import make_nzp
    from test_phase2 import import_dxf, nova_like_dxf

    monkeypatch.setenv("NOVA_LEGENDEN_HOME", str(tmp_path / "home"))
    nzp = make_nzp(tmp_path / "v2.nzp", "Test.Elektroinstallationen.V2.CH", [
        ("10", "10-10", "Schalter, Schema 0, UP"),
        ("20", "20-10", "Schalter, Schema 0, AP"),
        ("230", "230-10", "Brandmelder, UP"),
        ("290", "290-99", "Funk-Gateway"),
    ])
    stencils = tmp_path / "Stencils nova19"
    stencils.mkdir()
    shutil.copy(SAMPLE, stencils / "Benutzerschablonen.n5q")
    s = config.load_settings()
    s.dataset_paths = [str(nzp)]
    s.company_folder = str(tmp_path / "firma")
    s.projects_folder = str(tmp_path / "Legenden")
    s.stencil_folder = str(tmp_path / "Stencils nova{nova}")
    config.save_settings(s)
    state = AppState()
    state.first_start()
    client = TestClient(create_app(state, ui_dir=tmp_path / "no-ui"))
    pid = client.post("/api/projects", json={"name": "Test", "nova_version": "19.2"}).json()["id"]
    data = client.get("/api/stencils", params={"project_id": pid}).json()
    assert data["found"] and data["files"] == ["Benutzerschablonen.n5q"] and data["nova"] == "19.2"
    entries = [e for st in data["sets"] for t in st["tabs"] for e in t["entries"]]
    known = [e for e in entries if e["symbol_key"]]
    assert known and all(e["family_key"] for e in known)
    # Nova 20 has no stencil folder here: nothing found, no error
    assert client.get("/api/stencils", params={"nova": "20"}).json()["found"] is False
    # proposal text: company text first, else the stencil name, else the catalogue name
    assert import_dxf(client, pid, nova_like_dxf(tmp_path / "eg.dxf")).status_code == 200
    names = client.get(f"/api/projects/{pid}/legend").json()["stencil_names"]
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    texts = {it["family_key"]: it["text"] for b in doc["blocks"] for it in b["items"] if it["kind"] == "symbol"}
    shared = [fk for fk in texts if fk in names]
    assert shared and all(texts[fk] == names[fk] for fk in shared)
    fk = shared[0]
    client.put("/api/descriptions", json={"family_key": fk, "text": "Firmentext gewinnt"})
    doc = client.post(f"/api/projects/{pid}/legend/propose").json()["doc"]
    assert any(it["text"] == "Firmentext gewinnt" for b in doc["blocks"] for it in b["items"])
