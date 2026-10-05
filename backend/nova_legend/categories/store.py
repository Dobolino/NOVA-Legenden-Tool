"""Company-wide categories and symbol assignments (edeco ag-Legenden-firma.sqlite).

The file lives in the company folder (for example T:\\_CAD\\NOVA-Legenden)
so every user shares the same categories. SQLite on a network share is
safe for this use as long as writes are short and rare:

* journal_mode DELETE (WAL does not work on network shares)
* a new connection per operation, busy timeout 10 s
* every change records user and time
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

from ..config import current_user
from .defaults import DATASET_RULES, DEFAULT_CATEGORIES, EXTRA_SHEETS, NAME_RULES

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, parent TEXT, layer TEXT,
    columns INTEGER DEFAULT 2, spacing REAL DEFAULT 4.55, sort INTEGER,
    hidden INTEGER DEFAULT 0, sheets TEXT DEFAULT '[]',
    updated_by TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS assignments (
    family_key TEXT PRIMARY KEY, categories TEXT NOT NULL,
    updated_by TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS options (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS mappings (
    source_key TEXT PRIMARY KEY, symbol_key TEXT NOT NULL, name TEXT,
    updated_by TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS layer_colors (
    name TEXT PRIMARY KEY, color TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS symbol_options (
    family_key TEXT PRIMARY KEY, show_fill INTEGER,
    updated_by TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS descriptions (
    family_key TEXT PRIMARY KEY, text TEXT NOT NULL, updated_by TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS log (ts TEXT, user TEXT, action TEXT, detail TEXT);
"""

DEFAULT_OPTIONS = {
    "merge_labels": True,        # "(Ohne Text)" etc. under the UP representative
    "merge_orientation": False,  # liegend / stehend stay separate symbols
    "show_empty_categories": False,
    "legend_by_category": True,
}

# Legend settings of the company (Allgemeinteil, admins, standard for new projects).
LEGEND_DEFAULTS = {
    "legend_general_path": "",     # DXF, DWG or template project folder on the server
    "legend_admins": [],           # Windows user names allowed to change these settings
    "legend_text_size": 2.5,       # mm, one size for all legend texts
    "legend_symbol_scale": 1.0,    # one scale for all symbols
    "legend_hatch_off": False,     # new legends: no hatches and light areas in symbols
    "legend_fill_off": False,      # new legends: no solid fills in symbols
    # changes to the rows of the general part, by normalised row text: the drawing on the
    # server stays the source, these are kept beside it ({text, hidden, links, by, at})
    "legend_general_rows": {},
}

# Bump when default categories gain number ranges; existing company files
# are extended once (only ranges that are not assigned anywhere yet).
DEFAULTS_VERSION = 2

CATEGORY_FIELDS = ("title", "parent", "layer", "columns", "spacing", "hidden", "sheets")


def normalize_sheets(values: list[str] | str) -> list[str]:
    """Clean number ranges: split on commas, trim, drop empty and duplicates."""
    parts = values.split(",") if isinstance(values, str) else [
        p for v in values for p in str(v).split(",")]
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CompanyStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as con:
            con.executescript(SCHEMA)
            if not con.execute("SELECT 1 FROM categories LIMIT 1").fetchone():
                self._seed(con)
                self._set_defaults_version(con)
            else:
                self._migrate(con)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=DELETE")
            yield con
            con.commit()
        finally:
            con.close()

    def _log(self, con: sqlite3.Connection, action: str, detail: str) -> None:
        con.execute("INSERT INTO log VALUES (?,?,?,?)", (_now(), current_user(), action, detail))

    def _seed(self, con: sqlite3.Connection) -> None:
        for sort, cat in enumerate(DEFAULT_CATEGORIES):
            d = asdict(cat)
            con.execute(
                "INSERT INTO categories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (d["id"], d["title"], d["parent"], d["layer"], d["columns"], d["spacing_mm"],
                 sort, 0, json.dumps(d["sheets"]), "system", _now()))
        self._log(con, "seed", "Standardkategorien angelegt")

    def _set_defaults_version(self, con: sqlite3.Connection) -> None:
        con.execute("INSERT OR REPLACE INTO options VALUES ('defaults_version', ?)",
                    (json.dumps(DEFAULTS_VERSION),))

    def _migrate(self, con: sqlite3.Connection) -> None:
        row = con.execute("SELECT value FROM options WHERE key='defaults_version'").fetchone()
        version = json.loads(row["value"]) if row else 1
        if version >= DEFAULTS_VERSION:
            return
        rows = {r["id"]: json.loads(r["sheets"] or "[]")
                for r in con.execute("SELECT id, sheets FROM categories")}
        used = {s for sheets in rows.values() for s in sheets}
        counts: dict[str, int] = {}
        for extra in EXTRA_SHEETS.values():
            for sheet in extra:
                counts[sheet] = counts.get(sheet, 0) + 1
        shared = {sheet for sheet, n in counts.items() if n > 1}
        added = []
        for cat_id, extra in EXTRA_SHEETS.items():
            if cat_id not in rows:
                continue
            # A range may be added if nobody uses it yet, or if the defaults
            # themselves put it into several categories (e.g. S_KombGr1).
            new = [s for s in extra if s not in rows[cat_id]
                   and (s not in used or s in shared)]
            if new:
                rows[cat_id] += new
                used.update(new)
                con.execute("UPDATE categories SET sheets=? WHERE id=?",
                            (json.dumps(rows[cat_id]), cat_id))
                added.append(f"{cat_id}: {', '.join(new)}")
        if "schema" not in rows:
            schema = next(c for c in DEFAULT_CATEGORIES if c.id == "schema")
            sort = con.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM categories").fetchone()[0]
            con.execute("INSERT INTO categories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (schema.id, schema.title, None, schema.layer, schema.columns,
                         schema.spacing_mm, sort, 0, "[]", "system", _now()))
            added.append("neue Kategorie schema")
        self._set_defaults_version(con)
        self._log(con, "migrate", f"Standard v{DEFAULTS_VERSION}: " + "; ".join(added))

    # -- options ---------------------------------------------------------------

    def options(self) -> dict:
        with self._tx() as con:
            stored = {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT * FROM options")}
        return {k: stored.get(k, v) for k, v in DEFAULT_OPTIONS.items()}

    def set_options(self, values: dict) -> dict:
        with self._tx() as con:
            for key, value in values.items():
                if key in DEFAULT_OPTIONS:
                    con.execute("INSERT OR REPLACE INTO options VALUES (?,?)", (key, json.dumps(value)))
            self._log(con, "options", json.dumps(values, ensure_ascii=False))
        return self.options()

    # -- legend settings (company-wide, admins only; checked by the API) ---------

    def legend_settings(self) -> dict:
        with self._tx() as con:
            stored = {r["key"]: json.loads(r["value"]) for r in con.execute(
                "SELECT * FROM options WHERE key LIKE 'legend_%'")}
        out = {k: stored.get(k, v) for k, v in LEGEND_DEFAULTS.items()}
        out["legend_admins"] = [str(a) for a in out["legend_admins"] if str(a).strip()]
        return out

    def set_legend_settings(self, values: dict) -> dict:
        with self._tx() as con:
            for key, value in values.items():
                if key in LEGEND_DEFAULTS and value is not None:
                    con.execute("INSERT OR REPLACE INTO options VALUES (?,?)", (key, json.dumps(value)))
            self._log(con, "legend_settings", json.dumps(values, ensure_ascii=False))
        return self.legend_settings()

    # -- categories ------------------------------------------------------------

    def categories(self) -> list[dict]:
        with self._tx() as con:
            rows = con.execute("SELECT * FROM categories ORDER BY sort, title").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["sheets"] = json.loads(d["sheets"] or "[]")
            d["hidden"] = bool(d["hidden"])
            out.append(d)
        return out

    def create_category(self, title: str, parent: str | None = None, layer: str = "") -> dict:
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "kategorie"
        cat_id = f"{base}-{uuid.uuid4().hex[:6]}"
        with self._tx() as con:
            sort = con.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM categories").fetchone()[0]
            con.execute(
                "INSERT INTO categories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (cat_id, title, parent, layer, 2, 4.55, sort, 0, "[]", current_user(), _now()))
            self._log(con, "category.create", f"{cat_id} {title}")
        return next(c for c in self.categories() if c["id"] == cat_id)

    def update_category(self, cat_id: str, values: dict) -> dict:
        sets, args = [], []
        for key in CATEGORY_FIELDS:
            if key in values:
                value = values[key]
                if key == "sheets":
                    value = json.dumps(normalize_sheets(value))
                if key == "hidden":
                    value = int(bool(value))
                sets.append(f"{key}=?")
                args.append(value)
        if not sets:
            raise ValueError("Keine Änderung angegeben")
        with self._tx() as con:
            cur = con.execute(
                f"UPDATE categories SET {', '.join(sets)}, updated_by=?, updated_at=? WHERE id=?",
                (*args, current_user(), _now(), cat_id))
            if cur.rowcount == 0:
                raise KeyError(cat_id)
            self._log(con, "category.update", f"{cat_id} {json.dumps(values, ensure_ascii=False)}")
        return next(c for c in self.categories() if c["id"] == cat_id)

    def delete_category(self, cat_id: str) -> None:
        with self._tx() as con:
            cur = con.execute("DELETE FROM categories WHERE id=?", (cat_id,))
            if cur.rowcount == 0:
                raise KeyError(cat_id)
            con.execute("UPDATE categories SET parent=NULL WHERE parent=?", (cat_id,))
            # Remove the category from manual assignments
            for row in con.execute("SELECT family_key, categories FROM assignments").fetchall():
                cats = [c for c in json.loads(row["categories"]) if c != cat_id]
                if cats:
                    con.execute("UPDATE assignments SET categories=? WHERE family_key=?",
                                (json.dumps(cats), row["family_key"]))
                else:
                    con.execute("DELETE FROM assignments WHERE family_key=?", (row["family_key"],))
            self._log(con, "category.delete", cat_id)

    def reorder(self, ids: list[str]) -> list[dict]:
        with self._tx() as con:
            for sort, cat_id in enumerate(ids):
                con.execute("UPDATE categories SET sort=? WHERE id=?", (sort, cat_id))
            self._log(con, "category.reorder", ",".join(ids))
        return self.categories()

    def reset_defaults(self) -> list[dict]:
        with self._tx() as con:
            con.execute("DELETE FROM categories")
            con.execute("DELETE FROM assignments")
            self._seed(con)
        return self.categories()

    # -- remembered decisions for unknown plan elements ---------------------------

    def mappings(self) -> dict[str, str]:
        with self._tx() as con:
            return {r["source_key"]: r["symbol_key"] for r in con.execute("SELECT * FROM mappings")}

    def set_mapping(self, source_key: str, symbol_key: str | None, name: str = "") -> None:
        """Remember which library symbol an element is (or "__ignore__"). None forgets it."""
        with self._tx() as con:
            if symbol_key is None:
                con.execute("DELETE FROM mappings WHERE source_key=?", (source_key,))
            else:
                con.execute("INSERT OR REPLACE INTO mappings VALUES (?,?,?,?,?)",
                            (source_key, symbol_key, name, current_user(), _now()))
            self._log(con, "mapping", f"{source_key} -> {symbol_key}")

    # -- layer colours learned from imported plans ----------------------------------

    def layer_colors(self) -> dict[str, str]:
        with self._tx() as con:
            return {r["name"]: r["color"] for r in con.execute("SELECT * FROM layer_colors")}

    def learn_layer_colors(self, colors: dict[str, str]) -> None:
        with self._tx() as con:
            for name, color in colors.items():
                if color:
                    con.execute("INSERT OR REPLACE INTO layer_colors VALUES (?,?,?)",
                                (name, color, _now()))

    # -- legend descriptions per family (company-wide) ----------------------------

    def descriptions(self) -> dict[str, str]:
        with self._tx() as con:
            return {r["family_key"]: r["text"] for r in con.execute("SELECT * FROM descriptions")}

    def description_rows(self) -> list[dict]:
        """All company texts with who saved them last, by family key."""
        with self._tx() as con:
            return [dict(r) for r in con.execute("SELECT * FROM descriptions ORDER BY family_key")]

    def set_description(self, family_key: str, text: str | None) -> None:
        """Standard legend text of a family. Empty or None goes back to the library name."""
        with self._tx() as con:
            if not (text or "").strip():
                con.execute("DELETE FROM descriptions WHERE family_key=?", (family_key,))
            else:
                con.execute("INSERT OR REPLACE INTO descriptions VALUES (?,?,?,?)",
                            (family_key, text.strip(), current_user(), _now()))
            self._log(con, "description", f"{family_key} -> {text}")

    # -- per family display options ----------------------------------------------

    def fill_settings(self) -> dict[str, bool]:
        """Families with an explicit fill choice: {family_key: show_fill}."""
        with self._tx() as con:
            return {r["family_key"]: bool(r["show_fill"])
                    for r in con.execute("SELECT family_key, show_fill FROM symbol_options")}

    def set_fill(self, family_key: str, show_fill: bool | None) -> None:
        """Show or hide filled areas and hatches of a family. None = default (shown)."""
        with self._tx() as con:
            if show_fill is None:
                con.execute("DELETE FROM symbol_options WHERE family_key=?", (family_key,))
            else:
                con.execute("INSERT OR REPLACE INTO symbol_options VALUES (?,?,?,?)",
                            (family_key, int(show_fill), current_user(), _now()))
            self._log(con, "fill", f"{family_key} -> {show_fill}")

    # -- assignments -------------------------------------------------------------

    def assignments(self) -> dict[str, list[str]]:
        with self._tx() as con:
            return {r["family_key"]: json.loads(r["categories"])
                    for r in con.execute("SELECT * FROM assignments")}

    def assign(self, family_key: str, category_ids: list[str] | None) -> None:
        """Set manual categories for a family. None or [] restores the automatic rule."""
        with self._tx() as con:
            if category_ids:
                con.execute("INSERT OR REPLACE INTO assignments VALUES (?,?,?,?)",
                            (family_key, json.dumps(category_ids), current_user(), _now()))
            else:
                con.execute("DELETE FROM assignments WHERE family_key=?", (family_key,))
            self._log(con, "assign", f"{family_key} -> {category_ids}")


def auto_categories(sheet: str, name: str, categories: list[dict],
                    dataset: str = "") -> tuple[list[str], str]:
    """Automatic rule: number range, then dataset rule, then name pattern, else Diverse."""
    ids = [c["id"] for c in categories if sheet in c["sheets"]]
    if ids:
        return ids, f"Nummernkreis {sheet}"
    known = {c["id"] for c in categories}
    for fragment, cat_id in DATASET_RULES:
        if cat_id in known and fragment in dataset:
            return [cat_id], "Datensatz"
    low = name.lower()
    for pattern, cat_id in NAME_RULES:
        if cat_id in known and re.search(pattern, low):
            return [cat_id], "Namensmuster"
    fallback = "diverse" if "diverse" in known else (categories[-1]["id"] if categories else "")
    return ([fallback] if fallback else []), "keine Regel"
