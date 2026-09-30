"""Tests for the program update (no network: fetch and download are faked)."""

from __future__ import annotations

import hashlib
import io

import pytest

from nova_legend import config, updater

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
