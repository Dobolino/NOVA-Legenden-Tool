"""Write the exported legend drawing as a vector PDF.

The PDF is drawn from the same ezdxf document as the DXF export, so both show the
same thing: symbols, texts, colours and the general part. ezdxf's drawing add-on
resolves every entity (blocks, hatches, line types, texts as outlines); a small
PDF writer turns the result into one page of the legend size plus a margin.
No package beyond ezdxf is needed.
"""

from __future__ import annotations

import zlib

PT_PER_MM = 72 / 25.4
MARGIN_MM = 10.0
LINE_MODES = ("original", "proportional")
# proportional line weights stay printable and do not turn into bars
PROPORTIONAL_MIN, PROPORTIONAL_MAX = 0.09, 0.50      # mm
DEFAULT_LINEWEIGHT = 0.25                             # mm, what CAD plots for «Standard»
_STROKES = ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE")


def build_pdf(doc, width_mm: float, height_mm: float, title: str = "", lines: str = "original") -> bytes:
    """``doc`` is the legend DXF (millimetres, origin bottom left, legend in
    0..width × 0..height). ``lines``: «original» keeps the line weights of the drawings,
    «proportional» makes them thinner or thicker with the size of each symbol."""
    if lines == "proportional":
        scale_lineweights(doc)
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import (BackgroundPolicy, ColorPolicy, Configuration,
                                             LineweightPolicy)
    from ezdxf.addons.drawing.recorder import Recorder

    recorder = Recorder()
    config = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.COLOR,
                           lineweight_policy=LineweightPolicy.ABSOLUTE)
    Frontend(RenderContext(doc), recorder, config=config).draw_layout(doc.modelspace(), finalize=True)
    player = recorder.player()
    box = player.bbox()
    # the legend area, grown if a drawing reaches past it (general part, long text)
    x0, y0, x1, y1 = 0.0, 0.0, width_mm, height_mm
    if box.has_data:
        x0, y0 = min(x0, box.extmin.x), min(y0, box.extmin.y)
        x1, y1 = max(x1, box.extmax.x), max(y1, box.extmax.y)
    writer = _PdfPage(x0 - MARGIN_MM, y0 - MARGIN_MM)
    player.replay(writer)
    return writer.document(x1 - x0 + 2 * MARGIN_MM, y1 - y0 + 2 * MARGIN_MM, title)


def scale_lineweights(doc) -> int:
    """Line weight of every stroke in a symbol block times the factor the block is drawn
    at (``doc.nl_line_factors``), kept between 0.09 and 0.5 mm. Changes the document in
    memory. Returns the number of changed strokes."""
    from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS

    factors = getattr(doc, "nl_line_factors", None) or {}
    valid = [v for v in VALID_DXF_LINEWEIGHTS if v > 0]
    changed = 0
    for name, factor in factors.items():
        if name not in doc.blocks or factor <= 0:
            continue
        for e in doc.blocks.get(name):
            if e.dxftype() not in _STROKES:
                continue
            lw = int(e.dxf.get("lineweight", -1))
            if lw < 0:
                try:
                    lw = int(doc.layers.get(e.dxf.layer).dxf.lineweight)
                except Exception:  # noqa: BLE001
                    lw = -3
            mm = lw / 100 if lw >= 0 else DEFAULT_LINEWEIGHT
            target = min(PROPORTIONAL_MAX, max(PROPORTIONAL_MIN, mm * factor)) * 100
            e.dxf.lineweight = min(valid, key=lambda v: abs(v - target))
            changed += 1
    return changed


def _rgb(color: str) -> str:
    c = (color or "#000000").lstrip("#")
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        r = g = b = 0
    return f"{r / 255:.3f} {g / 255:.3f} {b / 255:.3f}"


class _PdfPage:
    """ezdxf BackendInterface that collects PDF drawing operators."""

    def __init__(self, ox: float, oy: float) -> None:
        self.ox, self.oy = ox, oy
        self.ops: list[str] = ["1 J 1 j"]          # round caps and joins like the CAD view
        self.min_lineweight = 0.13
        self.stroke = self.fill = self.width = None

    # -- coordinates and state --

    def _p(self, v) -> str:
        return f"{(v.x - self.ox) * PT_PER_MM:.2f} {(v.y - self.oy) * PT_PER_MM:.2f}"

    def _stroke_state(self, props) -> None:
        color = _rgb(props.color)
        if color != self.stroke:
            self.ops.append(f"{color} RG")
            self.stroke = color
        width = max(self.min_lineweight, props.lineweight or 0.0) * PT_PER_MM
        if width != self.width:
            self.ops.append(f"{width:.3f} w")
            self.width = width

    def _fill_state(self, props) -> None:
        color = _rgb(props.color)
        if color != self.fill:
            self.ops.append(f"{color} rg")
            self.fill = color

    def _path(self, path, close: bool) -> None:
        from ezdxf.path import Command

        if not len(path):
            return
        self.ops.append(f"{self._p(path.start)} m")
        current = path.start
        for cmd in path.commands():
            if cmd.type == Command.MOVE_TO:
                self.ops.append(f"{self._p(cmd.end)} m")
            elif cmd.type == Command.LINE_TO:
                self.ops.append(f"{self._p(cmd.end)} l")
            elif cmd.type == Command.CURVE3_TO:      # quadratic: as cubic
                c1 = current + (cmd.ctrl - current) * (2 / 3)
                c2 = cmd.end + (cmd.ctrl - cmd.end) * (2 / 3)
                self.ops.append(f"{self._p(c1)} {self._p(c2)} {self._p(cmd.end)} c")
            elif cmd.type == Command.CURVE4_TO:
                self.ops.append(f"{self._p(cmd.ctrl1)} {self._p(cmd.ctrl2)} {self._p(cmd.end)} c")
            current = cmd.end
        if close:
            self.ops.append("h")

    # -- BackendInterface --

    def configure(self, config) -> None:
        if config.min_lineweight:
            self.min_lineweight = max(0.05, config.min_lineweight * 25.4 / 300)

    def set_background(self, color) -> None:
        pass                                          # paper stays white

    def draw_point(self, pos, properties) -> None:
        self.draw_line(pos, pos, properties)

    def draw_line(self, start, end, properties) -> None:
        self._stroke_state(properties)
        self.ops.append(f"{self._p(start)} m {self._p(end)} l S")

    def draw_solid_lines(self, lines, properties) -> None:
        lines = list(lines)
        if not lines:
            return
        self._stroke_state(properties)
        self.ops.append(" ".join(f"{self._p(a)} m {self._p(b)} l" for a, b in lines) + " S")

    def draw_path(self, path, properties) -> None:
        if not len(path):
            return
        self._stroke_state(properties)
        self._path(path, close=False)
        self.ops.append("S")

    def draw_filled_paths(self, paths, properties) -> None:
        paths = [p for p in paths if len(p)]
        if not paths:
            return
        self._fill_state(properties)
        for p in paths:
            self._path(p, close=True)
        self.ops.append("f*")

    def draw_filled_polygon(self, points, properties) -> None:
        vertices = list(points.vertices())
        if len(vertices) < 3:
            return
        self._fill_state(properties)
        self.ops.append(f"{self._p(vertices[0])} m " + " ".join(f"{self._p(v)} l" for v in vertices[1:]) + " h f*")

    def draw_image(self, image_data, properties) -> None:
        pass                                          # legends have no images

    def clear(self) -> None:
        pass

    def finalize(self) -> None:
        pass

    def enter_entity(self, entity, properties) -> None:
        pass

    def exit_entity(self, entity) -> None:
        pass

    # -- file --

    def document(self, width_mm: float, height_mm: float, title: str) -> bytes:
        content = zlib.compress("\n".join(self.ops).encode("ascii"))
        w, h = width_mm * PT_PER_MM, height_mm * PT_PER_MM
        safe = title.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w:.2f} {h:.2f}] /Contents 4 0 R /Resources << >> >>".encode(),
            f"<< /Length {len(content)} /Filter /FlateDecode >>\nstream\n".encode() + content + b"\nendstream",
            b"<< /Title (" + safe.encode("latin-1", "replace") + b") /Producer (NOVA-Legenden) >>",
        ]
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
        out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
        out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 5 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)
