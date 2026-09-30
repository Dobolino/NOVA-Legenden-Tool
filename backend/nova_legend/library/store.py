"""Local symbol library: a SQLite cache built from the Nova datasets.

The cache (library.sqlite in the local data folder) is rebuilt when a
dataset file changes (path, size or modification time). Families and
categories are computed in memory because they depend on settings.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

from ..parser.dataset import Dataset
from ..render.svg import has_fill, render_svg
from .families import FamilyOptions, build_families, family_key, label_variant, orientation

# Bump when the parser or renderer output changes: forces a rebuild of the cache
SCHEMA_VERSION = 7

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY, file TEXT, version TEXT, long_name TEXT,
    predecessor TEXT, fingerprint TEXT, symbol_count INTEGER);
CREATE TABLE IF NOT EXISTS symbols (
    key TEXT PRIMARY KEY, dataset TEXT, item TEXT, graphic_id TEXT, sheet TEXT,
    name TEXT, part_name TEXT, sheet_name TEXT, folder TEXT, folder_path TEXT,
    stencils TEXT, kind TEXT, mounting TEXT, label_variant TEXT, orientation TEXT,
    engine TEXT, lib_ref TEXT, files_3d TEXT, attributes TEXT, geometry TEXT,
    points TEXT, svg TEXT, svg_nofill TEXT, has_fill INTEGER);
CREATE INDEX IF NOT EXISTS ix_symbols_item ON symbols(dataset, item);
"""


@dataclass
class LibSymbol:
    """Symbol row as used by the API (geometry loaded on demand)."""

    key: str
    dataset: str
    item: str
    graphic_id: str
    sheet: str
    name: str
    part_name: str
    sheet_name: str
    folder: str
    kind: str
    mounting: str | None
    label_variant: str
    orientation: str
    svg: str
    files_3d: list[str] = field(default_factory=list)
    svg_nofill: str = ""       # same symbol without filled areas and hatches
    has_fill: bool = False


def fingerprint(path: Path) -> str:
    st = path.stat()
    return f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}"


class Library:
    """Thread-safe access to the library cache."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._symbols: dict[str, LibSymbol] = {}
        self._families_cache: dict[FamilyOptions, dict] = {}
        with self._connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
            row = con.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            columns = {r[1] for r in con.execute("PRAGMA table_info(symbols)")}
            stale = bool(columns) and not {"svg_nofill", "has_fill"} <= columns
            if not row or int(row[0]) != SCHEMA_VERSION or stale:
                # The cache is rebuilt from the datasets: drop the old tables so
                # new columns exist (CREATE IF NOT EXISTS would keep the old ones).
                con.executescript("DROP TABLE IF EXISTS symbols; DROP TABLE IF EXISTS datasets;")
                con.execute("INSERT OR REPLACE INTO meta VALUES ('schema', ?)", (str(SCHEMA_VERSION),))
            con.executescript(SCHEMA)
        self._load_memory()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    # -- building ------------------------------------------------------------

    def sync(self, dataset_paths: list[str]) -> dict:
        """Bring the cache in line with the given dataset files.

        Returns a report: added, unchanged, removed, errors.
        """
        report = {"neu": [], "unveraendert": [], "entfernt": [], "fehler": [], "doppelt": []}
        wanted: dict[str, Path] = {}
        for p in dataset_paths:
            path = Path(p)
            if path.is_file():
                wanted[str(path.resolve())] = path
            else:
                report["fehler"].append(f"Datei nicht gefunden: {p}")
        with self._lock, self._connect() as con:
            existing = {r["file"]: dict(r) for r in con.execute("SELECT * FROM datasets")}
            seen_ids: set[str] = set()
            for resolved, path in wanted.items():
                fp = fingerprint(path)
                old = existing.get(resolved)
                if old and old["fingerprint"] == fp:
                    report["unveraendert"].append(old["id"])
                    seen_ids.add(old["id"])
                    continue
                try:
                    ds = Dataset(path)
                except Exception as exc:  # noqa: BLE001 - report any broken file
                    report["fehler"].append(f"{path.name}: {exc}")
                    continue
                if ds.info.id in seen_ids:
                    # Same dataset in a second file: keep the first, no error
                    report["doppelt"].append(str(path))
                    continue
                self._store_dataset(con, ds, resolved, fp)
                seen_ids.add(ds.info.id)
                report["neu"].append(ds.info.id)
            for file, row in existing.items():
                if row["id"] not in seen_ids:
                    con.execute("DELETE FROM symbols WHERE dataset=?", (row["id"],))
                    con.execute("DELETE FROM datasets WHERE id=?", (row["id"],))
                    report["entfernt"].append(row["id"])
        self._load_memory()
        return report

    @staticmethod
    def _store_dataset(con: sqlite3.Connection, ds: Dataset, file: str, fp: str) -> None:
        con.execute("DELETE FROM symbols WHERE dataset=?", (ds.info.id,))
        con.execute("DELETE FROM datasets WHERE id=?", (ds.info.id,))
        rows = []
        for s in ds.symbols:
            geo = s.geometry
            drawable = bool(geo and geo.primitives)
            svg = render_svg(geo, None, show_points=False) if drawable else ""
            filled = drawable and has_fill(geo)
            svg_nofill = render_svg(geo, None, show_points=False, show_fill=False) if filled else svg
            rows.append((
                s.key, s.dataset, s.item, s.graphic_id, s.sheet, s.name, s.part_name,
                s.sheet_name, s.folder, json.dumps(s.folder_path, ensure_ascii=False),
                json.dumps(s.stencils, ensure_ascii=False), s.kind, s.mounting,
                label_variant(s.name), orientation(s.name), s.engine, s.lib_ref,
                json.dumps(s.files_3d, ensure_ascii=False),
                json.dumps(s.attributes, ensure_ascii=False),
                json.dumps(geo.to_dict(), ensure_ascii=False) if geo else None,
                json.dumps(geo.points if geo else {}), svg, svg_nofill, int(filled),
            ))
        con.executemany(f"INSERT INTO symbols VALUES ({','.join('?' * 24)})", rows)
        con.execute("INSERT INTO datasets VALUES (?,?,?,?,?,?,?)", (
            ds.info.id, file, ds.info.version, ds.info.long_name,
            ds.info.raw.get("PredecessorID", ""), fp, len(ds.symbols)))

    # -- reading -------------------------------------------------------------

    def _load_memory(self) -> None:
        with self._connect() as con:
            rows = con.execute(
                "SELECT key, dataset, item, graphic_id, sheet, name, part_name, sheet_name, "
                "folder, kind, mounting, label_variant, orientation, svg, files_3d, svg_nofill, "
                "has_fill FROM symbols"
            ).fetchall()
        self._symbols = {
            r["key"]: LibSymbol(
                r["key"], r["dataset"], r["item"], r["graphic_id"], r["sheet"], r["name"],
                r["part_name"], r["sheet_name"], r["folder"], r["kind"], r["mounting"],
                r["label_variant"], r["orientation"], r["svg"], json.loads(r["files_3d"] or "[]"),
                r["svg_nofill"] or "", bool(r["has_fill"]))
            for r in rows
        }
        self._families_cache.clear()

    def datasets(self) -> list[dict]:
        with self._connect() as con:
            return [dict(r) for r in con.execute("SELECT * FROM datasets ORDER BY id DESC")]

    def symbols(self) -> list[LibSymbol]:
        return list(self._symbols.values())

    def symbol(self, key: str) -> LibSymbol | None:
        return self._symbols.get(key)

    def symbol_detail(self, key: str) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM symbols WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        out = dict(row)
        for col in ("folder_path", "stencils", "files_3d", "attributes", "geometry", "points"):
            out[col] = json.loads(out[col]) if out[col] else None
        return out

    def families(self, options: FamilyOptions) -> dict:
        """Families per dataset: {family_id: Family}. family_id = dataset|key."""
        cached = self._families_cache.get(options)
        if cached is not None:
            return cached
        by_ds: dict[str, list[LibSymbol]] = {}
        for s in self._symbols.values():
            by_ds.setdefault(s.dataset, []).append(s)
        result = {}
        for ds_id, syms in by_ds.items():
            for fam in build_families(syms, options):  # type: ignore[arg-type]
                result[f"{ds_id}|{fam.key}"] = fam
        self._families_cache[options] = result
        return result

    @staticmethod
    def family_key_of(name: str, options: FamilyOptions) -> str:
        return family_key(name, options)
