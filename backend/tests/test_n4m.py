"""Nova model drawings (.n4m): same container and object records as .n4d."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from nova_legend.importer.n4d import read_n4d

from test_phase2 import import_dxf
from test_phase3 import env  # noqa: F401 - fixture

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
N4M = SAMPLES / "gro04p.n4m"
N4D = SAMPLES / "3_1.OG.n4d"


@pytest.mark.skipif(not N4M.is_file(), reason="sample gro04p.n4m missing")
def test_model_drawing_is_read_like_a_plan():
    result = read_n4d(N4M, "n4m")
    assert result.format == "n4m"
    assert result.info["datasets"].get("Trimble.Elektroinstallationen.CH")
    assert len(result.layers) > 10 and any(layer.color for layer in result.layers)
    counts = {f.item: f.count for f in result.found}
    assert sum(counts.values()) > 100
    assert counts.get("230-170", 0) > 0                      # Brandmelder
    assert all(f.source_key.startswith("n4d:") for f in result.found)


@pytest.mark.skipif(not N4D.is_file(), reason="sample 3_1.OG.n4d missing")
def test_n4m_upload_is_imported_and_shown_as_n4m(env, tmp_path):  # noqa: F811
    client, _ = env
    pid = client.post("/api/projects", json={"name": "Modell"}).json()["id"]
    model = tmp_path / "3_1.OG.n4m"               # same records: an N4D under the N4M name
    shutil.copy2(N4D, model)
    res = import_dxf(client, pid, model, name="1. OG")
    assert res.status_code == 200, res.text
    plan = client.get(f"/api/projects/{pid}").json()["plans"][0]
    assert plan["format"] == "n4m"
    # reimport of the same floor as N4D keeps the rows (same source keys)
    again = import_dxf(client, pid, N4D, name="1. OG", plan_id=plan["id"])
    assert again.status_code == 200
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["plans"][0]["format"] == "n4d" and detail["plans"][0]["versions"] == 2


def test_other_files_are_refused(env, tmp_path):  # noqa: F811
    client, _ = env
    pid = client.post("/api/projects", json={"name": "X"}).json()["id"]
    bad = tmp_path / "plan.pdf"
    bad.write_bytes(b"%PDF")
    res = import_dxf(client, pid, bad)
    assert res.status_code == 400 and "N4M" in res.json()["detail"]


V1_NZP = SAMPLES / "Elektroinstallationen.CH.nzp"


@pytest.mark.skipif(not V1_NZP.is_file(), reason="sample Elektroinstallationen.CH.nzp missing")
def test_linear_luminaires_of_the_catalogue_are_symbols():
    from nova_legend.parser.dataset import Dataset

    ds = Dataset(V1_NZP)
    led = {s.item: s for s in ds.symbols if s.sheet == "140"}
    assert len(led) == 53 and led["LED_8"].name == "LED-Langfeldleuchte 8W"
    assert led["LED_8"].kind == "Engine" and led["LED_8"].graphic_id == "ST"
    assert led["LED_8"].attributes["L"] == "800" and led["LED_8"].geometry.primitives
