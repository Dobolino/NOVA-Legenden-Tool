"""Read-only analysis of Nova N4D files (plans, macros, legends).

Status (Phase 0): the Elements stream is NOT fully decoded. This module
extracts what is reliably identifiable today:

* container streams and metadata (olefile)
* all MFC CStrings (FF FE FF <len> UTF-16LE) with their byte offsets
* Nova objects that reference a dataset: element name, catalogue code,
  graphic variant and layer
* free text elements with their placement frame (x, y, rotation)
* embedded ACIS solids (version stamp)

Everything here only reads. Writing N4D is a later phase (Phase 6).
"""

from __future__ import annotations

import math
import re
import struct
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import olefile

CSTRING = re.compile(rb"\xff\xfe\xff")
CODE_RE = re.compile(r"^[0-9A-Za-z_]+-[0-9A-Za-z_]+$")
# Marker that follows the CString of a free text element
TEXT_TAIL = b"\x33\x04\x00\x00\x00\x66\x3e\x00"
ONE = b"\x00\x00\x00\x00\x00\x00\xf0\x3f"   # little endian double 1.0
ACIS_RE = re.compile(rb"Plancal nova[\x00-\x20]*.{0,4}?(\d+\.\d+\.\d+ NT)", re.S)


@dataclass
class CStr:
    offset: int
    end: int
    text: str


@dataclass
class Frame:
    """2D placement: 3x3 matrix followed by extra values (layout seen in N4D)."""

    offset: int
    rotation: float
    mirrored: bool
    size: float
    x: float
    y: float


@dataclass
class N4DObject:
    name: str
    dataset: str
    sheet: str
    item: str
    graphic_id: str | None = None
    graphic_name: str | None = None
    layer: str | None = None
    offset: int = 0


@dataclass
class N4DText:
    text: str
    offset: int
    frame: Frame | None


@dataclass
class N4DReport:
    path: str
    streams: dict[str, int]
    header_strings: list[str]
    elements_magic: str
    elements_field: int
    version_stream: str
    acis_versions: list[str]
    datasets: dict[str, int]
    objects: list[N4DObject] = field(default_factory=list)
    texts: list[N4DText] = field(default_factory=list)
    frames: list[Frame] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)
    fonts: list[str] = field(default_factory=list)
    string_count: int = 0

    def code_counts(self) -> Counter:
        return Counter(o.item for o in self.objects)


def read_cstrings(buf: bytes) -> list[CStr]:
    out = []
    for m in CSTRING.finditer(buf):
        o = m.start() + 3
        if o >= len(buf):
            break
        length = buf[o]
        o += 1
        if length == 0xFF:
            length = struct.unpack_from("<H", buf, o)[0]
            o += 2
        raw = buf[o:o + 2 * length]
        if len(raw) != 2 * length:
            continue
        out.append(CStr(m.start(), o + 2 * length, raw.decode("utf-16le", "replace")))
    return out


def _strip_guid(text: str) -> str:
    """Element names carry a 16 byte GUID inside the string. Remove it."""
    if len(text) > 8:
        tail = text[-8:]
        if any(ord(c) > 0x2FF for c in tail):
            return text[:-8]
    return text


def find_frames(buf: bytes) -> list[Frame]:
    """Locate 3x3 placement matrices (rotation / mirror) and read x, y.

    Layout found in Legende_edeco20.n4d:
        +0   9 doubles  matrix (row major, last row 0 0 1)
        +80  double     size-like value
        +98  double     x
        +106 double     y
    """
    frames = []
    for m in re.finditer(re.escape(ONE), buf):
        start = m.start() - 64
        if start < 0 or start + 114 > len(buf):
            continue
        mat = struct.unpack_from("<9d", buf, start)
        if mat[2] != 0 or mat[5] != 0 or mat[6] != 0 or mat[7] != 0:
            continue
        if abs(math.hypot(mat[0], mat[1]) - 1) > 1e-6 or abs(math.hypot(mat[3], mat[4]) - 1) > 1e-6:
            continue
        size = struct.unpack_from("<d", buf, start + 80)[0]
        x, y = struct.unpack_from("<2d", buf, start + 98)
        det = mat[0] * mat[4] - mat[1] * mat[3]
        frames.append(Frame(start, round(math.degrees(math.atan2(mat[1], mat[0])), 4),
                            det < 0, size, x, y))
    return frames


def analyse(path: str | Path) -> N4DReport:
    path = Path(path)
    ole = olefile.OleFileIO(str(path))
    streams = {"/".join(s): ole.get_size("/".join(s)) for s in ole.listdir()}
    header = ole.openstream("Header").read() if ole.exists("Header") else b""
    version = ole.openstream("Version").read() if ole.exists("Version") else b""
    elements = ole.openstream("Elements").read()
    ole.close()

    header_strings = [s.text for s in read_cstrings(header)]
    strings = read_cstrings(elements)
    acis = sorted({m.group(1).decode("ascii", "replace") for m in ACIS_RE.finditer(elements)})

    report = N4DReport(
        path=str(path),
        streams=streams,
        header_strings=header_strings,
        elements_magic=elements[:4].hex(" "),
        elements_field=struct.unpack_from("<I", elements, 4)[0],
        version_stream=version.hex(" "),
        acis_versions=acis,
        datasets=dict(Counter(s.text for s in strings if s.text.startswith("Trimble."))),
        string_count=len(strings),
    )

    # -- objects referencing a dataset -----------------------------------
    current: N4DObject | None = None
    last_name = ""
    for i, s in enumerate(strings):
        t = s.text
        if i + 1 < len(strings) and (strings[i + 1].text.startswith("elektro\\")
                                     or strings[i + 1].text.startswith("novaleiste\\")):
            last_name = _strip_guid(t)
        if t.startswith("Trimble.") and i + 2 < len(strings):
            sheet, item = strings[i + 1].text, strings[i + 2].text
            nxt = strings[i + 3].text if i + 3 < len(strings) else ""
            if nxt.startswith("2D-"):
                if current and current.item == item and current.graphic_id is None:
                    current.graphic_id = nxt
                    current.graphic_name = strings[i + 4].text if i + 4 < len(strings) else None
                continue
            current = N4DObject(last_name, t, sheet, item, offset=s.offset)
            report.objects.append(current)
        elif current and current.layer is None and re.match(r"^(E_|X_)", t):
            current.layer = t

    # -- free texts with placement ----------------------------------------
    frames = find_frames(elements)
    report.frames = frames
    frame_starts = [f.offset for f in frames]
    for s in strings:
        if elements[s.end:s.end + 8] != TEXT_TAIL or not s.text or s.text == "?!":
            continue
        frame = next((frames[k] for k, fo in enumerate(frame_starts)
                      if s.end < fo < s.end + 200), None)
        report.texts.append(N4DText(s.text, s.offset, frame))

    report.layers = sorted({s.text for s in strings
                            if re.match(r"^(E_|X_)[\w.\-äöüÄÖÜ ]+$", s.text)})
    report.fonts = sorted({s.text for s in strings
                           if s.text.lower().endswith((".ttf", ".shx")) or s.text in ("Arial",)})
    return report
