"""Backend parts of the UI rework: native dialogs, category states for the layers tab."""

from __future__ import annotations

import pytest

from nova_legend import dialogs
from nova_legend.projects.colors import category_state, category_usage, pick_category_layer

from test_phase3 import env  # noqa: F401 - fixture
from test_phase2 import import_dxf, nova_like_dxf

LAYERS = [{"name": "E_232.5_Licht", "color": "#ff0000"}, {"name": "E_Leer", "color": ""},
          {"name": "E_Leitung_Licht", "color": "#00ff00"}, {"name": "E_233_Leuchten", "color": "#0000ff"}]


def state_for(category_layer, used, override=None):
    picked = pick_category_layer(category_layer, LAYERS, {}, override)
    return picked, category_state(picked, LAYERS, used)


def test_automatic_layer_by_tail_after_bkp_number():
    picked, st = state_for("E_Licht", 3)
    assert picked["layer"] == "E_232.5_Licht"
    assert st["state"] == "automatisch" and not st["layer_missing"] and not st["no_color"]


def test_used_category_without_matching_layer_needs_a_choice():
    picked, st = state_for("E_Steuerung", 2)
    assert picked["layer"] == "" and st["state"] == "waehlen"
    assert "E_Steuerung" in picked["reason"]


def test_unused_category_is_marked_as_such():
    _, st = state_for("E_Steuerung", 0)
    assert st["state"] == "unbenutzt" and st["used"] == 0
    _, st = state_for("E_Licht", 0)          # a layer would match, still not used
    assert st["state"] == "unbenutzt"


def test_manual_choice_wins_and_missing_layer_differs_from_layer_without_colour():
    _, st = state_for("E_Licht", 0, override="E_Leer")
    assert st["state"] == "manuell" and st["no_color"] and not st["layer_missing"]
    _, st = state_for("E_Licht", 1, override="E_Weg")
    assert st["state"] == "manuell" and st["layer_missing"] and not st["no_color"]


def test_usage_counts_current_apparatus_per_category():
    rows = [{"total": 3, "categories": ["licht"]}, {"total": 0, "categories": ["bma"]},
            {"total": 2, "categories": ["licht", "schema"]}]
    assert category_usage(rows) == {"licht": 5, "schema": 2}


def test_project_detail_carries_category_state(env):  # noqa: F811
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Test"}).json()["id"]
    data = import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf")).json()
    states = {c["id"]: c for c in data["category_colors"]}
    assert all(c["state"] in {"automatisch", "manuell", "waehlen", "unbenutzt"} for c in states.values())
    assert any(c["used"] > 0 for c in states.values())
    assert any(c["state"] == "unbenutzt" for c in states.values())


class FakeWindow:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def create_file_dialog(self, kind, directory="", allow_multiple=False, file_types=()):
        self.calls.append((kind, directory, file_types))
        return self.answer


@pytest.fixture()
def fake_webview(monkeypatch):
    import sys
    import types

    mod = types.SimpleNamespace(OPEN_DIALOG=10, FOLDER_DIALOG=20)
    monkeypatch.setitem(sys.modules, "webview", mod)
    yield
    dialogs.attach(None)


def test_dialog_without_window_reports_unavailable(env):  # noqa: F811
    client, _ = env
    dialogs.attach(None)
    assert client.get("/api/status").json()["dialogs"] is False
    assert client.post("/api/dialog/folder", json={}).json() == {"available": False, "path": None}
    assert client.post("/api/dialog/unbekannt", json={}).status_code == 404


def test_dialog_returns_chosen_path_and_none_on_cancel(env, fake_webview):  # noqa: F811
    client, tmp = env
    window = FakeWindow(("C:\\Daten\\Elektro.V2.CH.nzp",))
    dialogs.attach(window)
    assert client.get("/api/status").json()["dialogs"] is True
    res = client.post("/api/dialog/dataset", json={"start": str(tmp)}).json()
    assert res == {"available": True, "path": "C:\\Daten\\Elektro.V2.CH.nzp"}
    kind, directory, types = window.calls[0]
    assert kind == 10 and directory == str(tmp) and "*.nzp" in types[0]
    window.answer = None                     # cancelled
    assert client.post("/api/dialog/folder", json={}).json() == {"available": True, "path": None}
    assert window.calls[1][0] == 20
