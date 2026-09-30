"""Regression tests for the Phase 1 review points (no Trimble files needed)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nova_legend import config
from nova_legend.api.app import AppState, create_app
from nova_legend.categories.store import CompanyStore, normalize_sheets

from synthetic import make_nzp

V2 = "Test.Elektroinstallationen.V2.CH"
V1 = "Test.Elektroinstallationen.CH"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_LEGENDEN_HOME", str(tmp_path / "home"))
    v2 = make_nzp(tmp_path / "v2.nzp", V2, [
        ("10", "10-10", "Schalter, Schema 0, UP"),
        ("20", "20-10", "Schalter, Schema 0, AP"),
        ("230", "230-10", "Brandmelder, UP"),
    ])
    v1 = make_nzp(tmp_path / "v1.nzp", V1, [
        ("10", "10-10", "Schalter, Schema 0, UP"),
    ])
    s = config.load_settings()
    s.dataset_paths = [str(v2), str(v1)]
    s.company_folder = str(tmp_path / "firma")
    config.save_settings(s)
    state = AppState()
    state.first_start()
    return TestClient(create_app(state, ui_dir=tmp_path / "no-ui"))


def counts(client, dataset=""):
    params = {"dataset": dataset} if dataset else {}
    return {c["id"]: c["family_count"] for c in client.get("/api/categories", params=params).json()["items"]}


# 2. parent: null makes a sub category a main category again -------------------

def test_parent_null_releases_sub_category(client):
    tel = client.put("/api/categories/telefon", json={"parent": None})
    assert tel.status_code == 200, tel.text
    assert tel.json()["parent"] is None
    # Fields that were not sent stay unchanged
    assert tel.json()["title"] == "Telefon" and tel.json()["layer"] == "E_Telefon"


def test_update_without_fields_is_rejected(client):
    assert client.put("/api/categories/telefon", json={}).status_code == 400


def test_title_null_is_ignored_not_cleared(client):
    res = client.put("/api/categories/telefon", json={"title": None, "columns": 3})
    assert res.status_code == 200
    assert res.json()["title"] == "Telefon" and res.json()["columns"] == 3


def test_parent_cannot_be_itself(client):
    assert client.put("/api/categories/telefon", json={"parent": "telefon"}).status_code == 400


# 3. number ranges: "230, 240" -> two ranges, no empty or duplicate entries -----

def test_normalize_sheets():
    assert normalize_sheets("230, 240") == ["230", "240"]
    assert normalize_sheets(["230,", "", " 240 ", "230", ",,"]) == ["230", "240"]


def test_sheets_saved_as_two_ranges(client):
    res = client.put("/api/categories/bma", json={"sheets": ["230, 240", "", "230"]})
    assert res.json()["sheets"] == ["230", "240"]


# 4. sidebar counts follow the chosen dataset -----------------------------------

def test_counts_per_dataset(client):
    assert counts(client, V2)["schalter"] == 1       # one family (UP + AP) in V2
    assert counts(client, V1)["schalter"] == 1
    assert counts(client)["schalter"] == 2           # both datasets
    assert counts(client, V1)["bma"] == 0
    assert counts(client, V2)["bma"] == 1


# 5. search finds a family by the code of any member -----------------------------

def test_search_by_ap_code_finds_family(client):
    res = client.get("/api/library/families", params={"q": "20-10", "dataset": V2}).json()
    assert res["total"] == 1
    assert res["items"][0]["representative"]["item"] == "10-10"   # tile still shows UP
    variants = client.get("/api/library/families",
                          params={"q": "20-10", "dataset": V2, "all_variants": True}).json()
    assert [i["representative"]["item"] for i in variants["items"]] == ["20-10"]


# Unchanged behaviour (confirmation) ----------------------------------------------

def test_manual_assignment_applies_to_v1_and_v2(client):
    fams = client.get("/api/library/families", params={"q": "schalter schema 0"}).json()["items"]
    assert len(fams) == 2
    client.put("/api/library/family/categories", params={"id": fams[0]["id"]},
               json={"categories": ["diverse"]})
    fams = client.get("/api/library/families", params={"q": "schalter schema 0"}).json()["items"]
    assert all(f["categories"] == ["diverse"] for f in fams)


def test_ranges_50_60_in_two_categories(tmp_path):
    cats = {c["id"]: c["sheets"] for c in CompanyStore(tmp_path / "f.sqlite").categories()}
    for sheet in ("50", "60"):
        assert sheet in cats["schalter"] and sheet in cats["steckdosen"]


# Further Nova datasets (Niederspannung, Schwachstrom) ----------------------------

def test_new_company_file_knows_extra_ranges(tmp_path):
    cats = {c["id"]: c["sheets"] for c in CompanyStore(tmp_path / "f.sqlite").categories()}
    assert "BMA" in cats["bma"] and "S_P0" in cats["schalter"]
    assert "S_KombGr1" in cats["schalter"] and "S_KombGr1" in cats["steckdosen"]
    assert "schema" in cats


def test_existing_company_file_is_extended_once(tmp_path):
    import json
    import sqlite3
    path = tmp_path / "f.sqlite"
    store = CompanyStore(path)
    # Simulate an old file: no extra ranges, no schema category, version 1,
    # and a user who put "BMA" into Diverse on purpose.
    con = sqlite3.connect(path)
    for cid, sheets in con.execute("SELECT id, sheets FROM categories").fetchall():
        from nova_legend.categories.defaults import EXTRA_SHEETS
        keep = [s for s in json.loads(sheets) if s not in EXTRA_SHEETS.get(cid, [])]
        con.execute("UPDATE categories SET sheets=? WHERE id=?", (json.dumps(keep), cid))
    con.execute("UPDATE categories SET sheets=? WHERE id='diverse'", (json.dumps(["101", "BMA"]),))
    con.execute("DELETE FROM categories WHERE id='schema'")
    con.execute("DELETE FROM options WHERE key='defaults_version'")
    con.commit()
    con.close()
    cats = {c["id"]: c["sheets"] for c in CompanyStore(path).categories()}
    assert "S_P0" in cats["schalter"] and "schema" in cats
    assert "BMA" not in cats["bma"] and "BMA" in cats["diverse"]   # user choice kept
    assert "version" not in " ".join(store.options())               # internal key hidden


def test_dataset_rule_for_schematics(tmp_path):
    from nova_legend.categories.store import auto_categories
    cats = CompanyStore(tmp_path / "f.sqlite").categories()
    assert auto_categories("LS_6_B_1P", "LS-Schalter", cats,
                           "Plancal.Niederspannung_E.2014-11-06")[0] == ["schema"]
