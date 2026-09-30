"""Tests for the company store and the REST API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nova_legend import config
from nova_legend.categories.store import CompanyStore, auto_categories

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
V2 = SAMPLES / "Elektroinstallationen.V2.CH.nzp"


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_LEGENDEN_HOME", str(tmp_path / "home"))
    return tmp_path


def test_company_store_crud(tmp_path):
    store = CompanyStore(tmp_path / "firma" / "firma.sqlite")
    cats = store.categories()
    assert cats[0]["title"] == "Allgemein"
    new = store.create_category("Photovoltaik")
    assert new["title"] == "Photovoltaik"
    store.update_category(new["id"], {"title": "PV-Anlage", "sheets": ["500"], "hidden": True})
    changed = next(c for c in store.categories() if c["id"] == new["id"])
    assert changed["title"] == "PV-Anlage" and changed["sheets"] == ["500"] and changed["hidden"]
    store.assign("steckdose t13", [new["id"], "steckdosen"])
    store.delete_category(new["id"])
    assert store.assignments() == {"steckdose t13": ["steckdosen"]}
    ids = [c["id"] for c in store.categories()][::-1]
    assert [c["id"] for c in store.reorder(ids)] == ids
    assert store.options()["merge_labels"] is True
    assert store.set_options({"merge_orientation": True})["merge_orientation"] is True


def test_company_store_shared_between_instances(tmp_path):
    path = tmp_path / "shared" / "firma.sqlite"
    a, b = CompanyStore(path), CompanyStore(path)
    a.create_category("Gemeinsam")
    assert any(c["title"] == "Gemeinsam" for c in b.categories())


def test_auto_categories_rules(tmp_path):
    cats = CompanyStore(tmp_path / "f.sqlite").categories()
    assert auto_categories("50", "Kombination", cats)[0] == ["schalter", "steckdosen"]
    assert auto_categories("xx", "Rauchmelder optisch", cats)[0] == ["bma"]
    assert auto_categories("xx", "Unbekannt", cats)[0] == ["diverse"]


def test_settings_roundtrip(home):
    s = config.load_settings()
    s.company_folder = str(home / "firma")
    config.save_settings(s)
    assert config.load_settings().company_folder == str(home / "firma")
    assert config.load_settings().company_db == home / "firma" / "firma.sqlite"


@pytest.mark.skipif(not V2.exists(), reason="sample dataset missing")
def test_api_library_flow(home):
    from nova_legend.api.app import AppState, create_app

    s = config.load_settings()
    s.dataset_paths = [str(V2)]
    s.company_folder = str(home / "firma")
    config.save_settings(s)
    state = AppState()
    state.first_start()
    client = TestClient(create_app(state, ui_dir=home / "no-ui"))

    status = client.get("/api/status").json()
    assert status["symbol_count"] == 2346

    res = client.get("/api/library/families", params={"q": "schalter schema 0"}).json()
    fam = next(i for i in res["items"] if i["title"] == "Schalter, Schema 0")
    assert fam["representative"]["mounting"] == "UP"
    assert fam["mountings"][0] == "UP"
    assert fam["categories"] == ["schalter"]

    variants = client.get("/api/library/families",
                          params={"q": "schalter schema 0", "all_variants": True}).json()
    assert variants["total"] > res["total"]

    updated = client.put("/api/library/family/categories", params={"id": fam["id"]},
                         json={"categories": ["diverse"]}).json()
    assert updated["categories"] == ["diverse"] and updated["category_source"] == "manuell"
    restored = client.put("/api/library/family/categories", params={"id": fam["id"]},
                          json={"categories": None}).json()
    assert restored["category_source"].startswith("Nummernkreis")

    detail = client.get("/api/library/symbol", params={"key": fam["representative"]["key"]}).json()
    assert detail["stats"] == {"line": 2, "arc": 1} and "<svg" in detail["svg_points"]

    cats = client.get("/api/categories").json()["items"]
    assert next(c for c in cats if c["id"] == "schalter")["family_count"] > 50
    assert client.post("/api/categories", json={"title": " "}).status_code == 400
