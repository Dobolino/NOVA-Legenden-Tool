"""Tests for the Nova DXF analysis."""

from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from nova_legend.analysis.dxf_probe import analyse_dxf, block_base_name

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
OG_DXF = SAMPLES / "3_1.OG.dxf"


def test_block_base_name():
    assert block_base_name("Steckdose T13_ UP_ 3-fach_A09QHENBUK") == "Steckdose T13_ UP_ 3-fach"
    assert block_base_name("Plankopf edeco18") == "Plankopf edeco18"


def test_synthetic_nova_like_dxf(tmp_path):
    doc = ezdxf.new("R2013")
    blk = doc.blocks.new("Steckdose T13_ UP_A09QHEN7UK")
    blk.add_circle((0, 0), 125)
    blk.add_attdef("TypID", (0, 0))
    ins = doc.modelspace().add_blockref("Steckdose T13_ UP_A09QHEN7UK", (1000, 2000),
                                        dxfattribs={"layer": "E_Licht"})
    ins.add_attrib("TypID", "90-10")
    ins.add_attrib("Herkunft", "Elektroinstallationen V2 CH 2025-09 edeco AG")
    doc.modelspace().add_blockref("Steckdose T13_ UP_A09QHEN7UK", (0, 0))
    path = tmp_path / "t.dxf"
    doc.saveas(path)
    info = analyse_dxf(path, {"steckdose t13_ up": {"90-10"}})
    assert info["erkennung"] == {"TypID": 1, "Blockname": 1}
    assert info["katalogcodes"] == {"90-10": 2}


@pytest.mark.skipif(not OG_DXF.exists(), reason="sample DXF missing")
def test_real_og_dxf():
    info = analyse_dxf(OG_DXF)
    assert info["dxf_version"] == "AC1027"
    assert info["erkennung"]["TypID"] == 147
    assert info["katalogcodes"]["90-30"] == 23
