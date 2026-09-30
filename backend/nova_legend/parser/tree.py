"""Reader and writer for the Nova "pool tree" serialization.

Every file inside a Nova dataset archive (.nzp: Graphic, Data, Folder,
Translation, Package, Set, UserInterface, Macro) uses the same layout:

    uint32                 number of pool entries N
    N x entry:
        uint16             pool index of this string
        CString            MFC string: FF FE FF <len> <UTF-16LE chars>
    uint16 stream          a node tree whose values are pool indices

A node in the uint16 stream is encoded as

    name            pool index of the node (element) name
    n_attr          number of attributes
    n_attr x (key, value)   pool indices
    n_children      number of child nodes
    children        recursively

The result is equivalent to a small XML document. The pool is
de-duplicated, so the same string is stored only once.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Iterator

CSTRING_MARKER = b"\xff\xfe\xff"


@dataclass
class Node:
    """One element of the tree (like an XML element)."""

    name: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.attrs.get(key, default)

    def find_all(self, name: str) -> Iterator["Node"]:
        """Yield all descendants (depth first) with the given element name."""
        for child in self.children:
            if child.name == name:
                yield child
            yield from child.find_all(name)

    def find(self, name: str) -> "Node | None":
        return next(self.find_all(name), None)


@dataclass
class PoolTree:
    """A parsed file: root node plus the original pool order (for round trips)."""

    root: Node
    pool_order: list[tuple[int, str]]


# ---------------------------------------------------------------------------
# CString helpers (shared with the N4D reader)
# ---------------------------------------------------------------------------

def read_cstring(buf: bytes, offset: int) -> tuple[str, int]:
    """Read an MFC Unicode CString at *offset*. Returns (text, new_offset)."""
    if buf[offset:offset + 3] != CSTRING_MARKER:
        raise ValueError(f"No CString marker at offset {offset}")
    offset += 3
    length = buf[offset]
    offset += 1
    if length == 0xFF:
        length = struct.unpack_from("<H", buf, offset)[0]
        offset += 2
        if length == 0xFFFF:
            length = struct.unpack_from("<I", buf, offset)[0]
            offset += 4
    raw = buf[offset:offset + 2 * length]
    if len(raw) != 2 * length:
        raise ValueError(f"CString at {offset} runs past end of data")
    return raw.decode("utf-16le", errors="surrogatepass"), offset + 2 * length


def write_cstring(text: str) -> bytes:
    """Encode *text* as an MFC Unicode CString."""
    data = text.encode("utf-16le", errors="surrogatepass")
    length = len(data) // 2
    if length < 0xFF:
        head = bytes([length])
    elif length < 0xFFFF:
        head = b"\xff" + struct.pack("<H", length)
    else:
        head = b"\xff\xff\xff" + struct.pack("<I", length)
    return CSTRING_MARKER + head + data


# ---------------------------------------------------------------------------
# Tree reader / writer
# ---------------------------------------------------------------------------

def parse(buf: bytes) -> PoolTree:
    """Parse one pool-tree file. Raises ValueError on any inconsistency."""
    count = struct.unpack_from("<I", buf, 0)[0]
    offset = 4
    pool: dict[int, str] = {}
    order: list[tuple[int, str]] = []
    for _ in range(count):
        index = struct.unpack_from("<H", buf, offset)[0]
        offset += 2
        text, offset = read_cstring(buf, offset)
        if index in pool:
            raise ValueError(f"Duplicate pool index {index}")
        pool[index] = text
        order.append((index, text))
    if sorted(pool) != list(range(count)):
        raise ValueError("Pool indices are not contiguous")

    rest = len(buf) - offset
    if rest % 2:
        raise ValueError("Tree stream has odd length")
    values = struct.unpack_from(f"<{rest // 2}H", buf, offset)
    pos = 0

    def take() -> int:
        nonlocal pos
        value = values[pos]
        pos += 1
        return value

    def read_node() -> Node:
        name = pool[take()]
        attrs: dict[str, str] = {}
        for _ in range(take()):
            key = pool[take()]
            attrs[key] = pool[take()]
        n_children = take()
        # Iterative-friendly: children lists can be large but shallow
        children = [read_node() for _ in range(n_children)]
        return Node(name, attrs, children)

    root = read_node()
    if pos != len(values):
        raise ValueError(f"Tree stream has {len(values) - pos} unread values")
    return PoolTree(root, order)


def serialize(tree: PoolTree | Node) -> bytes:
    """Write a tree back to bytes.

    If a PoolTree with its original pool order is given and no new strings
    were added, the output is byte-identical to the input file.
    """
    if isinstance(tree, PoolTree):
        root, order = tree.root, list(tree.pool_order)
    else:
        root, order = tree, []

    index_of = {text: idx for idx, text in order}

    def intern(text: str) -> int:
        if text not in index_of:
            idx = len(order)
            order.append((idx, text))
            index_of[text] = idx
        return index_of[text]

    values: list[int] = []

    def emit(node: Node) -> None:
        values.append(intern(node.name))
        values.append(len(node.attrs))
        for key, value in node.attrs.items():
            values.append(intern(key))
            values.append(intern(value))
        values.append(len(node.children))
        for child in node.children:
            emit(child)

    emit(root)
    if len(order) > 0xFFFF:
        raise ValueError("Pool too large for 16-bit references")

    out = bytearray(struct.pack("<I", len(order)))
    for idx, text in order:
        out += struct.pack("<H", idx)
        out += write_cstring(text)
    out += struct.pack(f"<{len(values)}H", *values)
    return bytes(out)
