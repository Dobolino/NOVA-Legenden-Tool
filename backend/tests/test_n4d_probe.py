"""Tests for the read-only N4D probe (needs the sample files)."""

from __future__ import annotations

from pathlib import Path

import pytest

from nova_legend.n4d.probe import analyse, read_cstrings

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
LEGEND = SAMPLES / "Legende_edeco20.n4d"


def test_read_cstrings_synthetic():
    data = b"\x00\x01" + b"\xff\xfe\xff\x03" + "Abc".encode("utf-16le") + b"\x00"
    strings = read_cstrings(data)
    assert [s.text for s in strings] == ["Abc"]


@pytest.mark.skipif(not LEGEND.exists(), reason="sample legend missing")
def test_legend_objects_and_texts():
    rep = analyse(LEGEND)
    assert rep.datasets == {"Trimble.Elektroinstallationen.CH": 200}
    codes = rep.code_counts()
    assert len(codes) == 94
    first = rep.objects[0]
    assert (first.item, first.graphic_id, first.layer) == ("130-10", "2D-10", "E_Licht")
    texts = {t.text: t for t in rep.texts}
    t = texts["UP-Wandleitung"]
    assert t.frame is not None
    assert (round(t.frame.x, 3), round(t.frame.y, 3)) == (126.775, 132.175)
    assert "E_Brandmeldeanlagen" in rep.layers
