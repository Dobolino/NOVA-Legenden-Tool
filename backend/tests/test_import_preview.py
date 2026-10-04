"""Import preview: changes of a floor before the plan file is stored."""

from __future__ import annotations

import ezdxf

from test_phase2 import V2_LONG, nova_like_dxf
from test_phase3 import env  # noqa: F401 - fixture


def post(client, pid, path, url="preview", name="EG", plan_id=None):
    data = {"name": name}
    if plan_id:
        data["plan_id"] = str(plan_id)
    with open(path, "rb") as fh:
        return client.post(f"/api/projects/{pid}/plans/{url}", data=data, files={"file": (path.name, fh)})


def smaller_plan(path):
    """Same floor, one UP switch left, the fire detector and the AP switch gone."""
    doc = ezdxf.new("R2013")
    doc.layers.add("E_Licht", color=5)
    blk = doc.blocks.new("Schalter_ Schema 0_ UP_A0TEST0000")
    blk.add_circle((0, 0), 125)
    ins = doc.modelspace().add_blockref(blk.name, (0, 0), dxfattribs={"layer": "E_Licht"})
    ins.add_attrib("TypID", "10-10")
    ins.add_attrib("Bez", "Schalter, Schema 0, UP")
    ins.add_attrib("Herkunft", f"{V2_LONG} edeco AG")
    doc.saveas(path)
    return path


def test_new_floor_preview_stores_nothing_until_confirmed(env):  # noqa: F811
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Vorschau"}).json()["id"]
    res = post(client, pid, nova_like_dxf(tmp / "eg.dxf"))
    assert res.status_code == 200, res.text
    pre = res.json()
    assert pre["existing"] is False and pre["plan"] is None and pre["floor"] == "EG"
    assert pre["total_before"] == 0 and pre["total_after"] == 5
    assert pre["summary"]["neu"] == pre["kinds_after"] and pre["summary"]["weg"] == 0
    assert [u["name"] for u in pre["new_unknown"]] == ["Gateway"]
    assert [w["level"] for w in pre["warnings"]] == ["info"]          # unknown element: nothing lost
    assert client.get(f"/api/projects/{pid}").json()["plans"] == []     # nothing stored
    done = client.post(f"/api/projects/{pid}/plans/commit", json={"token": pre["token"]})
    assert done.status_code == 200 and [p["name"] for p in done.json()["plans"]] == ["EG"]
    again = client.post(f"/api/projects/{pid}/plans/commit", json={"token": pre["token"]})
    assert again.status_code == 410                                     # a token is used once


def test_reimport_preview_shows_losses_first_and_warns(env):  # noqa: F811
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Reimport"}).json()["id"]
    first = post(client, pid, nova_like_dxf(tmp / "eg.dxf"))
    plan = client.post(f"/api/projects/{pid}/plans/commit", json={"token": first.json()["token"]}).json()["plans"][0]
    pre = post(client, pid, smaller_plan(tmp / "eg-neu.dxf"), plan_id=plan["id"]).json()
    assert pre["existing"] is True and pre["plan"]["name"] == "EG"
    assert pre["total_before"] == 5 and pre["total_after"] == 1
    kinds = [c["kind"] for c in pre["changes"]]
    assert kinds == sorted(kinds, key=["weg", "geaendert", "neu"].index)   # losses first
    texts = " ".join(w["text"] for w in pre["warnings"])
    assert "ganz weg: «Brandmelder»" in texts and "Stark weniger: «Schalter, Schema 0» 4 → 1" in texts
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["plans"][0]["versions"] == 1                           # still the old import
    done = client.post(f"/api/projects/{pid}/plans/commit", json={"token": pre["token"]}).json()
    assert done["plans"][0]["versions"] == 2


def test_same_file_again_and_discard(env):  # noqa: F811
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Gleich"}).json()["id"]
    plan_file = nova_like_dxf(tmp / "eg.dxf")
    first = post(client, pid, plan_file).json()
    plan = client.post(f"/api/projects/{pid}/plans/commit", json={"token": first["token"]}).json()["plans"][0]
    pre = post(client, pid, plan_file, plan_id=plan["id"]).json()
    assert pre["changes"] == [] and pre["unchanged"] > 0
    assert pre["warnings"][0]["text"].startswith("Gleiche Datei")
    assert client.delete(f"/api/projects/{pid}/plans/preview/{pre['token']}").status_code == 200
    assert client.post(f"/api/projects/{pid}/plans/commit", json={"token": pre["token"]}).status_code == 410
    assert post(client, pid, plan_file, plan_id=999).status_code == 404


def test_warning_thresholds():
    from nova_legend.projects.preview import warnings

    def result(before, after, changes=()):
        return {"total_before": before, "total_after": after, "changes": list(changes), "new_unknown": []}

    assert warnings(result(100, 89), True)[0]["text"] == "11 Apparate weniger als bisher (11 %)."
    assert warnings(result(100, 92), True) == []                   # 8 % is normal planning
    assert warnings(result(20, 16), True) == []                    # 4 fewer: below the minimum
    assert warnings(result(0, 50), False) == []                    # a new floor has nothing to lose
    fmt = warnings(result(10, 10), True, "n4d", "dxf")
    assert fmt[0]["level"] == "info" and "Bisher N4D, neu DXF" in fmt[0]["text"]


def test_a_stale_preview_cannot_overwrite_a_newer_import(env):  # noqa: F811
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Veraltet"}).json()["id"]
    first = post(client, pid, nova_like_dxf(tmp / "eg.dxf")).json()
    plan = client.post(f"/api/projects/{pid}/plans/commit", json={"token": first["token"]}).json()["plans"][0]
    old = post(client, pid, smaller_plan(tmp / "klein.dxf"), plan_id=plan["id"]).json()     # preview A
    newer = post(client, pid, nova_like_dxf(tmp / "eg2.dxf"), plan_id=plan["id"]).json()     # preview B
    assert client.post(f"/api/projects/{pid}/plans/commit", json={"token": newer["token"]}).status_code == 200
    stale = client.post(f"/api/projects/{pid}/plans/commit", json={"token": old["token"]})
    assert stale.status_code == 409 and "seit der Vorschau geändert" in stale.json()["detail"]
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["plans"][0]["versions"] == 2                       # preview A did not land
    switch = next(r for r in detail["rows"] if r["title"] == "Schalter, Schema 0")
    assert switch["total"] == 4
    assert client.post(f"/api/projects/{pid}/plans/commit", json={"token": old["token"]}).status_code == 410
