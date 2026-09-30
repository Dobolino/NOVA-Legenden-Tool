"""Phase 0: analyse the sample files and write the control outputs.

Usage (from the project root):

    python -m nova_legend.analysis.phase0 --samples samples --out output/phase0

Writes:
    symbole_<dataset>.json     all symbols with geometry
    familien_<dataset>.json    UP/AP families
    kontrolle_<dataset>.html   control page (name + rendered symbol)
    familien_<dataset>.html    family groups with representative
    n4d_<file>.json            N4D analysis per file
    legende_rekonstruktion.html  legend texts at their decoded positions
    zusammenfassung.json       key figures for the report
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ..categories.defaults import DEFAULT_CATEGORIES, category_for
from ..library.families import build_families, label_variant
from ..n4d.probe import analyse
from ..parser.dataset import Dataset, Symbol
from ..render.svg import render_svg

CAT_TITLE = {c.id: c.title for c in DEFAULT_CATEGORIES}

PAGE_CSS = """
:root { --bg:#fafafa; --fg:#1b1b1b; --muted:#666; --card:#fff; --line:#ddd; --acc:#1971c2; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161616; --fg:#eee; --muted:#aaa; --card:#222; --line:#3a3a3a; --acc:#74c0fc; }
}
body { margin:0; padding:16px; background:var(--bg); color:var(--fg); font:14px Arial, sans-serif; }
h1 { font-size:20px; margin:0 0 8px; } h2 { font-size:16px; margin:24px 0 8px; }
.bar { position:sticky; top:0; background:var(--bg); padding:8px 0; display:flex; gap:8px;
       flex-wrap:wrap; z-index:2; border-bottom:1px solid var(--line); }
input, select { padding:6px; font-size:14px; background:var(--card); color:var(--fg);
                border:1px solid var(--line); border-radius:4px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:8px; }
.c { background:var(--card); border:1px solid var(--line); border-radius:6px; padding:6px;
     text-align:center; font-size:11px; overflow:hidden; }
.c svg { display:block; margin:0 auto; color:var(--fg); }
.c .n { font-weight:bold; margin-top:4px; word-wrap:break-word; }
.c .m { color:var(--muted); }
.rep { outline:2px solid var(--acc); }
.tag { display:inline-block; padding:0 4px; border-radius:3px; border:1px solid var(--line); margin:1px; }
.fam { background:var(--card); border:1px solid var(--line); border-radius:6px; padding:8px; margin:8px 0; }
.fam .grid { grid-template-columns:repeat(auto-fill, minmax(120px, 1fr)); }
.warn { color:#e8590c; }
.ph { width:96px; height:96px; margin:0 auto; display:flex; align-items:center; justify-content:center;
      border:1px dashed var(--line); color:var(--muted); font-size:10px; }
"""

FILTER_JS = """
<script>
const q = document.getElementById('q'), cat = document.getElementById('cat'),
      mnt = document.getElementById('mnt'), cnt = document.getElementById('cnt');
function f() {
  const t = q.value.toLowerCase(), c = cat.value, m = mnt.value; let n = 0;
  document.querySelectorAll('[data-s]').forEach(e => {
    const ok = (!t || e.dataset.s.includes(t)) && (!c || e.dataset.c === c) && (!m || e.dataset.m === m);
    e.style.display = ok ? '' : 'none'; if (ok) n++;
  });
  cnt.textContent = n + ' sichtbar';
}
[q, cat, mnt].forEach(e => e.addEventListener('input', f)); f();
</script>
"""


def symbol_record(sym: Symbol, fam_key: str, fam_title: str, is_rep: bool) -> dict:
    cat_id, reason = category_for(sym.sheet, sym.name)
    return {
        "key": sym.key,
        "dataset": sym.dataset,
        "name": sym.name,
        "bauteil": sym.part_name,
        "katalogcode": sym.item,
        "grafik_id": sym.graphic_id,
        "nummernkreis": sym.sheet,
        "blatt": sym.sheet_name,
        "ordner": sym.folder,
        "ordnerpfad": sym.folder_path,
        "schablonen": sym.stencils,
        "montageart": sym.mounting,
        "beschriftungsvariante": label_variant(sym.name),
        "familie": fam_key,
        "familie_titel": fam_title,
        "up_vertreter": is_rep,
        "kategorie": cat_id,
        "kategorie_grund": reason,
        "typ": sym.kind,
        "platzierung": sym.place_mode,
        "engine": sym.engine,
        "lib_verweis": sym.lib_ref,
        "geometrie": sym.geometry.to_dict() if sym.geometry else None,
        "anschlusspunkte": sym.geometry.points if sym.geometry else {},
        "konstruktionspunkte": sym.geometry.cpoints if sym.geometry else {},
        "verweise_3d": sym.files_3d,
    }


def card(sym: Symbol, cat_id: str, is_rep: bool, size: int = 96) -> str:
    if sym.geometry and sym.geometry.primitives:
        pic = render_svg(sym.geometry, size, title=sym.name)
    else:
        label = {"Engine": "parametrisch (Engine)", "Symbol": f"Lib {sym.lib_ref}"}.get(sym.kind, "keine Geometrie")
        pic = f'<div class="ph">{html.escape(label)}</div>'
    search = " ".join([sym.name, sym.item, sym.folder, sym.part_name]).lower()
    return (f'<div class="c{" rep" if is_rep else ""}" data-s="{html.escape(search)}" '
            f'data-c="{cat_id}" data-m="{sym.mounting or "-"}">{pic}'
            f'<div class="n">{html.escape(sym.name)}</div>'
            f'<div class="m">{html.escape(sym.item)} · {html.escape(sym.graphic_id)} · '
            f'{html.escape(sym.mounting or "-")}</div>'
            f'<div class="m">{html.escape(CAT_TITLE.get(cat_id, cat_id))}</div></div>')


def write_control_page(ds: Dataset, reps: set[str], out: Path) -> None:
    cats = Counter()
    cards = []
    for sym in ds.symbols:
        cat_id, _ = category_for(sym.sheet, sym.name)
        cats[cat_id] += 1
        cards.append(card(sym, cat_id, sym.key in reps))
    cat_opts = "".join(f'<option value="{c.id}">{html.escape(c.title)} ({cats[c.id]})</option>'
                       for c in DEFAULT_CATEGORIES if cats[c.id])
    mnt = Counter(s.mounting or "-" for s in ds.symbols)
    mnt_opts = "".join(f'<option value="{k}">{k} ({v})</option>' for k, v in sorted(mnt.items()))
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Symbolkontrolle {html.escape(ds.info.id)}</title><style>{PAGE_CSS}</style></head><body>
<h1>Symbolkontrolle: {html.escape(ds.info.long_name)} (Version {html.escape(ds.info.version)})</h1>
<p>{len(ds.symbols)} 2D-Symbole. Blauer Rahmen: UP-Vertreter der Familie.
Orange Punkte: Anschlusspunkte NP, blaue Punkte: WP/übrige.</p>
<div class="bar"><input id="q" placeholder="Suche Name oder Code" size="30">
<select id="cat"><option value="">Alle Kategorien</option>{cat_opts}</select>
<select id="mnt"><option value="">Alle Montagearten</option>{mnt_opts}</select>
<span id="cnt"></span></div>
<div class="grid">{''.join(cards)}</div>{FILTER_JS}</body></html>"""
    out.write_text(page, encoding="utf-8")


def write_family_page(ds: Dataset, families, out: Path) -> None:
    blocks = []
    multi = [f for f in families if len(f.members) > 1]
    for fam in multi:
        cat_id, _ = category_for(fam.representative.sheet, fam.representative.name)
        conflicts = "".join(f'<div class="warn">⚠ {html.escape(c)}</div>' for c in fam.conflicts)
        cards = "".join(card(m, cat_id, m is fam.representative, 72) for m in fam.members)
        search = (fam.title + " " + " ".join(m.item for m in fam.members)).lower()
        blocks.append(
            f'<div class="fam" data-s="{html.escape(search)}" data-c="{cat_id}" '
            f'data-m="{"konflikt" if fam.conflicts else "ok"}">'
            f'<b>{html.escape(fam.title)}</b> '
            + "".join(f'<span class="tag">{html.escape(m)}</span>' for m in fam.mountings)
            + f'{conflicts}<div class="grid">{cards}</div></div>')
    n_conf = sum(1 for f in multi if f.conflicts)
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Symbolfamilien {html.escape(ds.info.id)}</title><style>{PAGE_CSS}</style></head><body>
<h1>Symbolfamilien (UP/AP): {html.escape(ds.info.long_name)}</h1>
<p>{len(families)} Familien, davon {len(multi)} mit mehreren Varianten und {n_conf} mit Hinweis.
Blauer Rahmen: vorgeschlagener UP-Vertreter.</p>
<div class="bar"><input id="q" placeholder="Suche" size="30">
<select id="cat"><option value="">Alle Kategorien</option>
{''.join(f'<option value="{c.id}">{html.escape(c.title)}</option>' for c in DEFAULT_CATEGORIES)}</select>
<select id="mnt"><option value="">Alle</option><option value="konflikt">nur mit Hinweis</option>
<option value="ok">ohne Hinweis</option></select><span id="cnt"></span></div>
{''.join(blocks)}{FILTER_JS}</body></html>"""
    out.write_text(page, encoding="utf-8")


def write_legend_page(report, lookup: dict[str, Symbol], out: Path) -> None:
    """Draw the decoded legend texts at their positions (N4D units)."""
    texts = [t for t in report.texts if t.frame]
    if not texts:
        return
    xs = [t.frame.x for t in texts]
    ys = [t.frame.y for t in texts]
    x0, x1, y0, y1 = min(xs) - 20, max(xs) + 90, min(ys) - 10, max(ys) + 10
    items = "".join(
        f'<text x="{t.frame.x:.3f}" y="{-t.frame.y:.3f}" font-size="2" '
        f'transform="rotate({-t.frame.rotation:.2f} {t.frame.x:.3f} {-t.frame.y:.3f})">'
        f'{html.escape(t.text)}</text>' for t in texts)
    rows = "".join(
        f"<tr><td>{html.escape(o.item)}</td><td>{html.escape(o.graphic_id or '')}</td>"
        f"<td>{html.escape(o.name)}</td><td>{html.escape(o.layer or '')}</td>"
        f"<td>{html.escape(lookup[o.item].name if o.item in lookup else '— nicht im Datensatz —')}</td></tr>"
        for o in report.objects)
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Legende rekonstruiert</title><style>{PAGE_CSS}
svg.l {{ width:100%; max-width:1000px; background:var(--card); border:1px solid var(--line); }}
svg.l text {{ fill:var(--fg); font-family:Arial; }}
table {{ border-collapse:collapse; width:100%; }} td, th {{ border:1px solid var(--line); padding:3px 6px; font-size:12px; }}
</style></head><body>
<h1>Legende_edeco20.n4d: dekodierte Texte an ihrer Position</h1>
<p>{len(texts)} Texte mit Position. Symbole der Legende sind als Objekte erkannt (Tabelle unten),
ihre Einfügepunkte sind noch nicht dekodiert.</p>
<svg class="l" viewBox="{x0:.2f} {-y1:.2f} {x1 - x0:.2f} {y1 - y0:.2f}">{items}</svg>
<h2>Erkannte Nova-Objekte ({len(report.objects)})</h2>
<table><tr><th>Code</th><th>Grafik</th><th>Name im Plan</th><th>Ebene</th><th>Name im Datensatz</th></tr>{rows}</table>
</body></html>"""
    out.write_text(page, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--samples", default="samples")
    ap.add_argument("--out", default="output/phase0")
    args = ap.parse_args(argv)
    samples, out = Path(args.samples), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"datasets": {}, "n4d": {}}
    lookups: dict[str, dict[str, Symbol]] = {}

    for nzp in sorted(samples.glob("*.nzp")):
        ds = Dataset(nzp)
        tag = ds.info.id.replace("Trimble.", "")
        families = build_families(ds.symbols)
        fam_of = {m.key: f for f in families for m in f.members}
        reps = {f.representative.key for f in families}
        records = [symbol_record(s, fam_of[s.key].key, fam_of[s.key].title, s.key in reps)
                   for s in ds.symbols]
        (out / f"symbole_{tag}.json").write_text(
            json.dumps({"dataset": ds.info.raw, "symbole": records}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        (out / f"familien_{tag}.json").write_text(
            json.dumps([f.to_dict() for f in families], ensure_ascii=False, indent=1), encoding="utf-8")
        write_control_page(ds, reps, out / f"kontrolle_{tag}.html")
        write_family_page(ds, families, out / f"familien_{tag}.html")
        lookups[ds.info.id] = {s.item: s for s in ds.symbols}

        warn = Counter(w.split(" in ")[0] for s in ds.symbols if s.geometry for w in s.geometry.warnings)
        prim = Counter()
        for s in ds.symbols:
            if s.geometry:
                prim.update(s.geometry.stats())
        cats = Counter(category_for(s.sheet, s.name)[0] for s in ds.symbols)
        summary["datasets"][ds.info.id] = {
            "datei": nzp.name,
            "version": ds.info.version,
            "stand": ds.info.long_name,
            "vorgaenger": ds.info.raw.get("PredecessorID"),
            "datenformat": ds.info.raw.get("DataFormat"),
            "symbole_2d": len(ds.symbols),
            "katalogcodes": len({s.item for s in ds.symbols}),
            "typen": dict(Counter(s.kind or "-" for s in ds.symbols)),
            "montagearten": dict(Counter(s.mounting or "-" for s in ds.symbols)),
            "mit_geometrie": sum(1 for s in ds.symbols if s.geometry and s.geometry.primitives),
            "mit_3d": sum(1 for s in ds.symbols if s.files_3d),
            "primitive": dict(prim),
            "warnungen": dict(warn),
            "familien": len(families),
            "familien_mehrere_varianten": sum(1 for f in families if len(f.members) > 1),
            "familien_mit_hinweis": sum(1 for f in families if f.conflicts),
            "kategorien": {CAT_TITLE[k]: v for k, v in cats.most_common()},
            "ohne_ordner": sum(1 for s in ds.symbols if not s.folder),
        }
        print(f"{ds.info.id}: {len(ds.symbols)} Symbole, {len(families)} Familien")

    for n4d in sorted(samples.glob("*.n4d")):
        rep = analyse(n4d)
        tag = n4d.stem
        data = {
            "datei": n4d.name,
            "stroeme": rep.streams,
            "header_strings": rep.header_strings,
            "elements_kennung": rep.elements_magic,
            "elements_feld": rep.elements_field,
            "version_strom": rep.version_stream,
            "acis_versionen": rep.acis_versions,
            "datensaetze": rep.datasets,
            "ebenen": rep.layers,
            "schriften": rep.fonts,
            "objekte": [o.__dict__ for o in rep.objects],
            "katalogcodes": dict(sorted(rep.code_counts().items())),
            "texte": [{"text": t.text, "x": t.frame.x if t.frame else None,
                       "y": t.frame.y if t.frame else None,
                       "drehung": t.frame.rotation if t.frame else None} for t in rep.texts],
        }
        (out / f"n4d_{tag}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        missing = defaultdict(list)
        for o in rep.objects:
            if "-" in o.item and o.item not in lookups.get(o.dataset, {}):
                missing[o.dataset].append(o.item)
        summary["n4d"][n4d.name] = {
            "objekte": len(rep.objects),
            "katalogcodes": len(rep.code_counts()),
            "texte": len(rep.texts),
            "texte_mit_position": sum(1 for t in rep.texts if t.frame),
            "datensaetze": rep.datasets,
            "acis": rep.acis_versions,
            "elements_feld": rep.elements_field,
            "ebenen": len(rep.layers),
            "codes_nicht_im_datensatz": {k: sorted(set(v)) for k, v in missing.items()},
        }
        if rep.texts:
            merged: dict[str, Symbol] = {}
            for ds_id in rep.datasets:
                merged.update(lookups.get(ds_id, {}))
            write_legend_page(rep, merged, out / f"legende_{tag}.html")
        print(f"{n4d.name}: {len(rep.objects)} Objekte, {len(rep.texts)} Texte")

    (out / "zusammenfassung.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
