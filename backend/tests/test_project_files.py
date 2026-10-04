"""File/SQLite failures must preserve the previous import and respect project bounds."""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from nova_legend.importer.model import Found, ImportResult
from nova_legend.projects.store import PLANS_DIR, ProjectManager
from test_phase2 import import_dxf, nova_like_dxf
from test_phase3 import env  # noqa: F401


@pytest.fixture()
def imported(tmp_path):
    project = ProjectManager(tmp_path / "projects").create("Test", "19.2")
    plan_id = project.add_plan("EG")
    source = tmp_path / "source.dxf"
    source.write_bytes(b"original plan bytes")
    version = project.store_import(plan_id, source, "eg.dxf", result(3))
    return project, plan_id, source, version


def result(count):
    return ImportResult("dxf", found=[Found("switch", "Schalter", count)])


def current_file(project, plan_id):
    with project.tx() as con:
        row = con.execute("SELECT v.stored_file FROM plans p JOIN plan_versions v "
                          "ON v.id=p.current_version WHERE p.id=?", (plan_id,)).fetchone()
    return project.folder / row["stored_file"]


def assert_original(project, plan_id, version, path):
    assert project.plans()[0]["current_version"] == version
    assert len(project.versions(plan_id)) == 1
    assert project.elements(version)[0]["count"] == 3
    assert current_file(project, plan_id) == path
    assert path.read_bytes() == b"original plan bytes"
    assert list((project.folder / PLANS_DIR).iterdir()) == [path]


@pytest.mark.parametrize("filename", ["eg.dxf", "eg-new.dxf"])
def test_database_failure_preserves_previous_file_and_version(imported, filename):
    project, plan_id, source, version = imported
    old = current_file(project, plan_id)
    source.write_bytes(b"replacement bytes")
    with project.tx() as con:
        con.execute("CREATE TRIGGER fail_elements BEFORE INSERT ON plan_elements "
                    "BEGIN SELECT RAISE(ABORT, 'simulated database failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="simulated database failure"):
        project.store_import(plan_id, source, filename, result(7))
    assert_original(project, plan_id, version, old)


def test_partial_copy_failure_preserves_previous_file(imported, monkeypatch):
    project, plan_id, source, version = imported
    old = current_file(project, plan_id)

    def fail_copy(incoming, target):
        target.write(b"partial upload")
        raise OSError("disk full")

    monkeypatch.setattr("nova_legend.projects.store.shutil.copyfileobj", fail_copy)
    with pytest.raises(OSError, match="disk full"):
        project.store_import(plan_id, source, "eg.dxf", result(7))
    assert_original(project, plan_id, version, old)


def test_failed_commit_preserves_previous_file_and_rolls_back_new_version(imported, monkeypatch):
    project, plan_id, source, version = imported
    old = current_file(project, plan_id)
    connect = sqlite3.connect
    fail = True

    class FailingCommit(sqlite3.Connection):
        def commit(self):
            nonlocal fail
            if fail:
                fail = False
                raise sqlite3.OperationalError("simulated commit failure")
            return super().commit()

    monkeypatch.setattr("nova_legend.projects.store.sqlite3.connect",
                        lambda *args, **kwargs: connect(*args, **kwargs, factory=FailingCommit))
    with pytest.raises(sqlite3.OperationalError, match="simulated commit failure"):
        project.store_import(plan_id, source, "eg.dxf", result(7))
    assert_original(project, plan_id, version, old)


def test_successful_same_name_import_switches_file_and_keeps_one_original(imported):
    project, plan_id, source, old_version = imported
    old = current_file(project, plan_id)
    source.write_bytes(b"replacement bytes")
    new_version = project.store_import(plan_id, source, "eg.dxf", result(7))
    new = current_file(project, plan_id)
    assert new != old
    assert not old.exists()
    assert new.read_bytes() == b"replacement bytes"
    assert project.elements(new_version)[0]["count"] == 7
    assert project.elements(old_version)[0]["count"] == 3
    assert list((project.folder / PLANS_DIR).iterdir()) == [new]


def test_concurrent_imports_merge_against_the_last_committed_version(imported, monkeypatch):
    project, plan_id, source, old_version = imported
    copying = threading.Event()
    release = threading.Event()
    from nova_legend.projects import store
    copy = store.shutil.copyfileobj
    first_copy = True

    def delayed_copy(incoming, target):
        nonlocal first_copy
        if first_copy:
            first_copy = False
            copying.set()
            assert release.wait(timeout=5)
        return copy(incoming, target)

    monkeypatch.setattr(store.shutil, "copyfileobj", delayed_copy)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(project.store_import, plan_id, source, "first.dxf",
                            ImportResult("dxf", found=[Found("first", "First", 2)]))
        try:
            assert copying.wait(timeout=5)
            second = pool.submit(project.store_import, plan_id, source, "second.dxf",
                                 ImportResult("dxf", found=[Found("second", "Second", 4)]))
        finally:
            release.set()
        first.result(timeout=10)
        last = second.result(timeout=10)
    assert project.plans()[0]["current_version"] == last
    assert {row["source_key"]: row["count"] for row in project.elements(last)} == {
        "switch": 0, "first": 0, "second": 4,
    }
    assert len(project.versions(plan_id)) == 3
    assert len(list((project.folder / PLANS_DIR).iterdir())) == 1


@pytest.mark.parametrize("stored", [
    "../../outside.txt", "Plaene/../../outside.txt", "Plaene/../projekt.nlproj",
    "projekt.nlproj", "/tmp/outside.txt", r"C:\outside.txt", r"C:outside.txt",
    r"\\server\share\outside.txt", r"Plaene\..\..\outside.txt",
])
@pytest.mark.parametrize("operation", ["import", "detach"])
def test_untrusted_stored_paths_are_rejected_without_changes(imported, stored, operation):
    project, plan_id, source, version = imported
    old = current_file(project, plan_id)
    with project.tx() as con:
        con.execute("UPDATE plan_versions SET stored_file=? WHERE id=?", (stored, version))
    with pytest.raises(ValueError, match="Ungültiger Pfad"):
        if operation == "import":
            project.store_import(plan_id, source, "new.dxf", result(7))
        else:
            project.detach_file(plan_id)
    assert old.read_bytes() == b"original plan bytes"
    assert project.plans()[0]["current_version"] == version
    assert project.plans()[0]["file_name"] == "eg.dxf"
    with project.tx() as con:
        assert con.execute("SELECT stored_file FROM plan_versions WHERE id=?", (version,)).fetchone()[0] == stored
    assert len(project.versions(plan_id)) == 1


@pytest.mark.parametrize("link_directory", [False, True])
@pytest.mark.parametrize("operation", ["import", "detach"])
def test_symlinks_cannot_delete_files_outside_project(imported, link_directory, operation, tmp_path):
    project, plan_id, source, version = imported
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "important.dxf"
    sentinel.write_bytes(b"keep this file")
    plans = project.folder / PLANS_DIR
    old = current_file(project, plan_id)
    if link_directory:
        old.unlink()
        plans.rmdir()
        link = plans
        target = outside
    else:
        link = plans / sentinel.name
        target = sentinel
    try:
        link.symlink_to(target, target_is_directory=link_directory)
    except OSError:
        pytest.skip("Symlinks are unavailable on this OS/user account")
    with project.tx() as con:
        con.execute("UPDATE plan_versions SET stored_file=? WHERE id=?",
                    (f"{PLANS_DIR}/{sentinel.name}", version))
    with pytest.raises(ValueError, match="Ungültiger Pfad"):
        if operation == "import":
            project.store_import(plan_id, source, "new.dxf", result(7))
        else:
            project.detach_file(plan_id)
    assert sentinel.read_bytes() == b"keep this file"


def test_detach_database_failure_restores_the_original_file(imported):
    project, plan_id, source, version = imported
    old = current_file(project, plan_id)
    with project.tx() as con:
        con.execute("CREATE TRIGGER fail_detach BEFORE UPDATE ON plan_versions "
                    "BEGIN SELECT RAISE(ABORT, 'simulated detach failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="simulated detach failure"):
        project.detach_file(plan_id)
    assert_original(project, plan_id, version, old)


def test_legacy_windows_relative_paths_still_work(imported):
    project, plan_id, source, version = imported
    old = current_file(project, plan_id)
    with project.tx() as con:
        con.execute("UPDATE plan_versions SET stored_file=? WHERE id=?",
                    (f"Plaene\\{old.name}", version))
    project.detach_file(plan_id)
    assert not old.exists()
    assert project.plans()[0]["file_name"] == ""
    assert project.elements(version)[0]["count"] == 3


def test_api_rejects_crafted_project_path_without_deleting_outside_file(env):
    client, tmp = env
    pid = client.post("/api/projects", json={"name": "Crafted"}).json()["id"]
    plan_id = import_dxf(client, pid, nova_like_dxf(tmp / "eg.dxf")).json()["plans"][0]["id"]
    project = ProjectManager(tmp / "Legenden").get(pid)
    sentinel = tmp / "outside-important.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with project.tx() as con:
        con.execute("UPDATE plan_versions SET stored_file='../../outside-important.txt'")
    response = client.post(f"/api/projects/{pid}/plans/{plan_id}/detach")
    assert response.status_code == 400
    assert "Ungültiger Pfad" in response.json()["detail"]
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert project.plans()[0]["file_name"] == "eg.dxf"
