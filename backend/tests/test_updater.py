"""Tests for the program update (no network: fetch and download are faked)."""

from __future__ import annotations

import hashlib
import io

import pytest

from nova_legend import config, updater

from test_phase1_fixes import client  # noqa: F401 - fixture

SETUP = b"MZ fake setup"


def release(tag: str, with_asset: bool = True) -> dict:
    assets = [{
        "name": "NOVA-Legenden-Setup-0.1.0.exe",
        "browser_download_url": "https://example.invalid/setup.exe",
        "size": len(SETUP),
        "digest": "sha256:" + hashlib.sha256(SETUP).hexdigest(),
    }] if with_asset else []
    return {"tag_name": tag, "assets": assets, "html_url": "https://example.invalid", "body": "x"}


def test_parse_tag():
    assert updater.parse_tag("v0.1.0-build.3") == ((0, 1, 0), 3)
    assert updater.parse_tag("v1.2") == ((1, 2), 0)
    assert updater.parse_tag("latest") is None


def test_check_newer_build(monkeypatch):
    monkeypatch.setattr(config, "build_number", lambda: 2)
    info = updater.check(lambda url: release(f"v{config.APP_VERSION}-build.3"))
    assert info.available and info.latest.endswith("(Build 3)")
    assert info.size == len(SETUP) and info.sha256


def test_check_same_build(monkeypatch):
    monkeypatch.setattr(config, "build_number", lambda: 3)
    info = updater.check(lambda url: release(f"v{config.APP_VERSION}-build.3"))
    assert not info.available and "neueste" in info.message


def test_check_network_error():
    def boom(url):
        raise OSError("offline")
    info = updater.check(boom)
    assert not info.available and "offline" in info.message


def test_download_verifies_checksum(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "build_number", lambda: 0)
    info = updater.check(lambda url: release("v9.9.9-build.1"))
    path = updater.download(info, tmp_path, opener=lambda req, timeout: io.BytesIO(SETUP))
    assert path.read_bytes() == SETUP
    info.sha256 = "0" * 64
    with pytest.raises(ValueError):
        updater.download(info, tmp_path, opener=lambda req, timeout: io.BytesIO(SETUP))


def test_stable_channel_reads_only_the_latest_normal_release(monkeypatch):
    monkeypatch.setattr(config, "build_number", lambda: 2)
    urls = []

    def fetch(url):
        urls.append(url)
        return release(f"v{config.APP_VERSION}-build.3")

    assert updater.check(fetch).available
    assert urls == [updater.API_URL]           # GitHub's "latest" never is a pre-release


def test_test_channel_takes_the_newest_build_including_pre_releases(monkeypatch):
    monkeypatch.setattr(config, "build_number", lambda: 5)
    v = config.APP_VERSION
    listing = [dict(release(f"v{v}-build.6"), prerelease=False),
               dict(release(f"v{v}-build.9"), prerelease=True),
               dict(release(f"v{v}-build.12"), draft=True),
               dict(release("nightly"), prerelease=True)]
    info = updater.check(lambda url: listing if url == updater.LIST_URL else {}, channel="test")
    assert info.available and info.latest.endswith("(Build 9)")
    monkeypatch.setattr(config, "build_number", lambda: 9)
    assert not updater.check(lambda url: listing, channel="test").available


def test_update_channel_is_a_setting(client):  # noqa: F811
    assert client.get("/api/status").json()["settings"]["update_channel"] == "stable"
    assert client.put("/api/settings", json={"update_channel": "test"}).status_code == 200
    assert client.get("/api/status").json()["settings"]["update_channel"] == "test"
    assert client.put("/api/settings", json={"update_channel": "beta"}).status_code == 422


def test_setup_starts_only_after_the_window_closed(monkeypatch, tmp_path):
    import threading
    from nova_legend import updater

    started, order = [], []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: started.append(args))
    closed = threading.Event()

    def shutdown():
        order.append("window closed" if not started else "setup first")
        closed.set()

    updater.install(tmp_path / "setup.exe", shutdown, fallback_after=30)
    assert closed.wait(5)
    assert started == [] and order == ["window closed"]
    # the main thread, after the window loop ended
    assert updater.launch_pending() is True
    assert started[0][0].endswith("setup.exe") and "/SILENT" in started[0]
    assert updater.launch_pending() is False          # only once
