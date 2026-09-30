"""DWG import: convert to DXF with the ODA File Converter, then read the DXF.

Command line of the converter:
    ODAFileConverter <input folder> <output folder> <version> <type> <recurse> <audit> [filter]
e.g. "ACAD2013" "DXF" "0" "1" "plan.dwg"
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .dxf import read_dxf
from .model import ImportResult


class ConverterMissing(RuntimeError):
    pass


def convert_dwg_to_dxf(dwg: Path, oda_exe: str, out_dir: Path, version: str = "ACAD2013") -> Path:
    if not oda_exe or not Path(oda_exe).exists():
        raise ConverterMissing(
            "Für DWG-Dateien wird der ODA File Converter gebraucht. Er ist nicht installiert. "
            "Alternative: Plan in Nova als DXF exportieren und diese Datei importieren.")
    in_dir = Path(tempfile.mkdtemp(prefix="nl_dwg_in_"))
    try:
        src = in_dir / dwg.name
        shutil.copy2(dwg, src)
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        proc = subprocess.run(
            [oda_exe, str(in_dir), str(out_dir), version, "DXF", "0", "1", dwg.name],
            capture_output=True, timeout=300, creationflags=flags)  # noqa: S603 - fixed program
        target = out_dir / (dwg.stem + ".dxf")
        if not target.exists():
            raise RuntimeError(f"ODA File Converter hat keine DXF-Datei erzeugt "
                               f"(Rückgabewert {proc.returncode}).")
        return target
    finally:
        shutil.rmtree(in_dir, ignore_errors=True)


def read_dwg(path: str | Path, oda_exe: str) -> ImportResult:
    out_dir = Path(tempfile.mkdtemp(prefix="nl_dwg_out_"))
    try:
        dxf = convert_dwg_to_dxf(Path(path), oda_exe, out_dir)
        result = read_dxf(dxf)
        result.format = "dwg"
        return result
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
