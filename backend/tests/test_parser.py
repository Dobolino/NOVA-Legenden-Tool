"""Tests for the Nova dataset parser.

Tests that need the real Trimble dataset are skipped when the sample files
are not present (they are not part of the repository).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from nova_legend.library.families import build_families, family_key, label_variant
from nova_legend.categories.defaults import category_for
from nova_legend.parser import geometry, tree
from nova_legend.parser.dataset import Dataset, detect_mounting

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
V2 = SAMPLES / "Elektroinstallationen.V2.CH.nzp"
V1 = SAMPLES / "Elektroinstallationen.CH.nzp"
needs_v2 = pytest.mark.skipif(not V2.exists(), reason="sample dataset missing")

SWITCH_GEOMETRY = (
    '((1)(("")()(0)((3)(((Line)((0.00557116;0.00807116)(0.0075649;0.00607742))))'
    '(((Line)((0.0017675;0.0042675)(0.00557116;0.00807116))))'
    '(((Arc)((0;0.0025)(0.0025;0.0025)(0.0025;0.0025)(0)))))((0))((0))((0))))'
    '((2)(("NP0")(0;0.0025;0))(("WP")(0;0;0)))((1)(("CP1")(0;0.0025;0)(0)))'
    '(-0.0025;0;0.0025;0.005;1)'
)


# -- tree format ------------------------------------------------------------

def test_tree_roundtrip_synthetic():
    root = tree.Node("Root", {}, [
        tree.Node("Item", {"ID": "10-10", "Description": "Schalter, UP"}),
        tree.Node("Item", {"ID": "10-20", "Description": "Größe äöü"}),
    ])
    data = tree.serialize(root)
    parsed = tree.parse(data)
    assert parsed.root.children[1].get("Description") == "Größe äöü"
    assert tree.serialize(parsed) == data


def test_cstring_long_length():
    text = "x" * 300
    encoded = tree.write_cstring(text)
    assert encoded[3] == 0xFF
    assert tree.read_cstring(encoded, 0)[0] == text


@needs_v2
@pytest.mark.parametrize("path", [V2, V1])
def test_tree_roundtrip_real_files(path):
    if not path.exists():
        pytest.skip("sample missing")
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.startswith("Lib/"):
                continue
            raw = zf.read(name)
            assert tree.serialize(tree.parse(raw)) == raw, name


# -- geometry ---------------------------------------------------------------

def test_geometry_switch():
    geo = geometry.parse_geometry(SWITCH_GEOMETRY)
    assert geo.stats() == {"line": 2, "arc": 1}
    arc = next(p for p in geo.primitives if p.kind == "arc")
    assert arc.data["full"] and arc.data["radius"] == pytest.approx(0.0025)
    assert geo.points["NP0"] == [0, 0.0025, 0]
    assert geo.bbox == [-0.0025, 0, 0.0025, 0.005]
    assert not geo.warnings


def test_geometry_text_and_fill():
    text = ('((1)(("X_Text")()(0)((0))((1)(((FlexPolygon)((2|0;0|0;0.005)((2)()((Arc)((0;0.0025)'
            '(0;0.005)(0;0)(1))))))))((0))((1)(((0.0025;0;0;0.0025)(0.004;0.0017))(("Arial")(0)(0))'
            '("2")))))((1)(("WP")(0;0;0)))((1)(("CP1")(0;0;0)(0)))(-0.0025;0;0.0025;0.005;1)')
    geo = geometry.parse_geometry(text)
    kinds = geo.stats()
    assert kinds == {"polygon": 1, "text": 1}
    txt = next(p for p in geo.primitives if p.kind == "text")
    assert txt.data["text"] == "2" and txt.data["font"] == "Arial"
    assert txt.data["height"] == pytest.approx(0.0025)
    poly = next(p for p in geo.primitives if p.kind == "polygon")
    assert poly.filled and poly.data["segments"][1]["type"] == "arc"
    assert len(geometry.flex_points(poly.data)) > 3


def test_mounting_detection():
    assert detect_mounting("Schalter, Schema 0, UP") == "UP"
    assert detect_mounting("Steckdose T23, NAP, 2-fach") == "NAP"
    assert detect_mounting("Leerdose - Kombi Gr.I, AP") == "AP"
    assert detect_mounting("Drehschalter") is None
    assert detect_mounting("UPS-Anlage") is None


def test_family_key_and_label_variant():
    assert family_key("Steckdose T23, NUP, 2-fach (Ohne Text)") == family_key("Steckdose T23, AP, 2-fach")
    assert label_variant("Antennensteckdose, UP (ohne Text)") == "ohne text"
    assert label_variant("Schalter, UP") == ""


def test_category_by_number_range():
    assert category_for("230")[0] == "bma"
    assert category_for("20")[0] == "schalter"
    assert category_for("xyz", "Rauchmelder")[0] == "bma"


# -- real dataset -------------------------------------------------------------

@needs_v2
def test_dataset_v2_loads():
    ds = Dataset(V2)
    assert ds.info.id == "Trimble.Elektroinstallationen.V2.CH"
    assert ds.info.version == "1.3.2"
    by_code = {(s.item, s.graphic_id): s for s in ds.symbols}
    sw = by_code[("10-10", "2D-10")]
    assert sw.name == "Schalter, Schema 0, UP"
    assert sw.mounting == "UP" and sw.folder == "Schalter UP"
    assert sw.geometry.stats() == {"line": 2, "arc": 1}
    assert "CH_UP_Schalter_Taster.ng3d" in sw.files_3d
    # every Geometry item parses without warnings
    assert not [s for s in ds.symbols if s.geometry and s.geometry.warnings]


@needs_v2
def test_families_up_representative():
    ds = Dataset(V2)
    fams = build_families(ds.symbols)
    fam = next(f for f in fams if f.key == family_key("Schalter, Schema 0, UP"))
    assert fam.representative.item == "10-10"
    assert {"UP", "AP", "NUP"} <= set(fam.mountings)


def test_combinations_in_two_categories():
    from nova_legend.categories.defaults import categories_for
    assert categories_for("50") == ["schalter", "steckdosen"]


def test_text_matrix_is_column_major():
    text = ('((1)(("X_Text")()(0)((0))((0))((0))((1)(((0;-0.0025;0.0025;0)(0.00126;0.00528))'
            '(("Arial")(0)(0))("T23")))))((0))((0))()')
    geo = geometry.parse_geometry(text)
    t = geo.primitives[0].data
    assert t["rotation"] == pytest.approx(90.0)
    assert t["height"] == pytest.approx(0.0025)
