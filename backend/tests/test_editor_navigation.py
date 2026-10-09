"""Exercise the actual React editor against an isolated local API and SQLite DB."""

from __future__ import annotations

import os
import re
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

playwright = pytest.importorskip("playwright.sync_api")

from nova_legend.api.app import create_app
from test_phase2 import import_dxf, nova_like_dxf
from test_phase3 import env  # noqa: F401 - isolated settings and catalogue


def launch_chromium(pw):
    """Chromium for the browser tests: NOVA_TEST_CHROMIUM, Playwright's own, or one found
    on the machine. Without any browser the tests are skipped locally; in CI (GitHub
    Actions sets CI=true) they must run, so a missing browser fails there."""
    candidates = [os.environ.get("NOVA_TEST_CHROMIUM") or None]
    candidates += sorted(str(p) for p in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome"))
    error = None
    for path in candidates:
        try:
            return pw.chromium.launch(executable_path=path, headless=True)
        except Exception as exc:  # noqa: BLE001 - try the next browser
            error = exc
    if os.environ.get("CI"):
        raise RuntimeError(f"Kein Chromium für die Browser-Tests: {error}")
    pytest.skip("Kein Chromium für die Browser-Tests gefunden (NOVA_TEST_CHROMIUM setzen)")


@pytest.fixture()
def editor(env):
    client, tmp = env
    ui = Path(__file__).resolve().parents[2] / "ui" / "dist"
    if not (ui / "index.html").is_file():
        pytest.skip("Build the UI with npm run build before browser tests")
    ids = []
    for name in ("Browser A", "Browser B"):
        pid = client.post("/api/projects", json={"name": name}).json()["id"]
        assert import_dxf(client, pid, nova_like_dxf(tmp / f"{name}.dxf")).status_code == 200
        doc = client.post(f"/api/projects/{pid}/legend/propose", json={}).json()["doc"]
        doc["title"]["text"] = name
        assert client.put(f"/api/projects/{pid}/legend", json={"doc": doc}).status_code == 200
        ids.append(pid)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(
        create_app(client.app.state.nova, ui_dir=ui), log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("Browser test API did not start")
        time.sleep(0.02)
    try:
        with playwright.sync_playwright() as pw:
            browser = launch_chromium(pw)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{port}")
            page.get_by_text("Browser A", exact=True).click()
            page.get_by_role("button", name="Legende", exact=True).click()
            page.get_by_role("button", name="T Titel", exact=True).click()
            field = page.get_by_label("Text", exact=True)
            playwright.expect(field).to_have_value("Browser A")
            playwright.expect(page.get_by_label("Textgrösse Titel", exact=True)).to_have_value("5")
            assert page.locator(".legend-project").count() == 0
            yield page, field, client, ids
            assert not errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


# the editor saves to one named legend: /legend?legend=<id>
LEGEND_URL = re.compile(r"/legend(\?.*)?$")


def title(client, pid):
    return client.get(f"/api/projects/{pid}/legend").json()["legend"]["doc"]["title"]["text"]


def test_the_wide_view_button_sits_on_the_settings_row(editor):
    page, _field, _client, _ids = editor
    floating = page.get_by_role("button", name="Einstellungen schwebend")
    playwright.expect(floating).to_be_visible()
    page.get_by_role("button", name=re.compile(r"Grossansicht$")).click()
    close = page.locator("button.btn", has_text="Grossansicht beenden")
    playwright.expect(close).to_be_visible()
    side_by_side = page.evaluate("""() => {
        const buttons = [...document.querySelectorAll("button")];
        const a = buttons.find((el) => el.textContent.includes("Einstellungen schwebend"))?.getBoundingClientRect();
        const b = buttons.find((el) => el.textContent.includes("Grossansicht beenden"))?.getBoundingClientRect();
        return Boolean(a && b && Math.abs(a.top - b.top) < 8 && b.left >= a.right - 4 && b.left - a.right < 24);
    }""")
    assert side_by_side


def test_a_symbol_can_take_the_section_colour(editor):
    page, _field, client, ids = editor
    item = page.locator("button.outline-item").filter(has_not_text="T Titel").first
    playwright.expect(item).to_be_visible()
    item.click()
    take = page.get_by_role("button", name="Farbe von Abschnitt übernehmen")
    playwright.expect(take).to_be_visible()
    playwright.expect(page.get_by_label("Symbolfarbe")).to_be_visible()
    with page.expect_response(LEGEND_URL) as saved:
        take.click()
    assert saved.value.ok
    doc = client.get(f"/api/projects/{ids[0]}/legend").json()["legend"]["doc"]
    picked = [(it["symbol_color"], b["style"]["symbol"])
              for b in doc["blocks"] for it in b["items"] if it.get("symbol_color")]
    assert len(picked) == 1 and picked[0][0] == picked[0][1]


def test_the_grid_starts_on_and_stays_off_once_switched(editor):
    page, _field, _client, _ids = editor
    grid = page.get_by_role("button", name="Raster anzeigen")
    playwright.expect(grid).to_have_attribute("aria-pressed", "true")
    grid.click()
    playwright.expect(grid).to_have_attribute("aria-pressed", "false")
    page.reload()
    page.get_by_text("Browser A", exact=True).click()
    page.get_by_role("button", name="Legende", exact=True).click()
    playwright.expect(page.get_by_role("button", name="Raster anzeigen")).to_have_attribute("aria-pressed", "false")


@pytest.mark.parametrize("destination", ["global_tab", "project_tab", "back", "project"])
def test_immediate_navigation_saves_to_the_original_project(editor, destination):
    page, field, client, (a, b) = editor
    # Reproduce the original cross-project bug with the destination's load delayed.
    page.evaluate(r"""() => {
        const original = window.fetch;
        window.fetch = async (...args) => {
            if (/\/Browser%20B\/legend(\?.*)?$/.test(String(args[0])) && (!args[1]?.method || args[1].method === 'GET'))
                await new Promise(resolve => setTimeout(resolve, 1400));
            return original(...args);
        };
    }""")
    field.fill("Last edit in A")
    if destination == "global_tab":
        page.get_by_role("button", name="Kategorien", exact=True).click()
        playwright.expect(page.get_by_role("button", name="Kategorien", exact=True)).to_have_class("tab active")
    elif destination == "project_tab":
        page.get_by_role("button", name="Gesamtliste", exact=False).click()
        playwright.expect(field).not_to_be_visible()
    elif destination == "back":
        page.get_by_role("button", name="← Alle Projekte", exact=True).click()
        playwright.expect(page.get_by_role("button", name="Legende erstellen", exact=True)).to_be_visible()
    else:
        page.get_by_role("combobox", name="Projekt wechseln", exact=True).select_option(b)
        playwright.expect(page.get_by_role("heading", name="Browser B", exact=True)).to_be_visible()
    page.wait_for_timeout(1700)
    assert title(client, a) == "Last edit in A"
    assert title(client, b) == "Browser B"


@pytest.mark.parametrize("destination", ["global_tab", "project_tab", "project"])
def test_failed_save_keeps_the_editor_open_and_can_be_retried(editor, destination):
    page, field, client, (a, b) = editor

    def fail_save(route):
        if route.request.method == "PUT":
            route.fulfill(status=503, content_type="application/json", body='{"detail":"Speicher nicht erreichbar"}')
        else:
            route.continue_()

    page.route(LEGEND_URL, fail_save)
    field.fill("Retry this edit")
    if destination == "global_tab":
        page.get_by_role("button", name="Kategorien", exact=True).click()
    elif destination == "project_tab":
        page.get_by_role("button", name="Gesamtliste", exact=False).click()
    else:
        page.get_by_role("combobox", name="Projekt wechseln", exact=True).select_option(b)
    playwright.expect(page.get_by_text("Legende nicht gespeichert:", exact=False)).to_be_visible()
    playwright.expect(field).to_have_value("Retry this edit")
    playwright.expect(page.get_by_role("combobox", name="Projekt wechseln", exact=True)).to_have_value(a)
    assert title(client, a) == "Browser A"
    page.unroute(LEGEND_URL, fail_save)
    page.get_by_role("button", name="Kategorien", exact=True).click()
    playwright.expect(page.get_by_role("button", name="Kategorien", exact=True)).to_have_class("tab active")
    assert title(client, a) == "Retry this edit"


def test_navigation_waits_for_an_inflight_autosave_and_then_saves_the_latest_edit(editor):
    page, field, client, (a, b) = editor
    page.evaluate(r"""() => {
        const original = window.fetch;
        window.legendWrites = [];
        window.fetch = async (...args) => {
            if (/\/legend(\?.*)?$/.test(String(args[0])) && args[1]?.method === 'PUT') {
                window.legendWrites.push(JSON.parse(args[1].body).doc.title.text);
                if (window.legendWrites.length === 1) {
                    window.saveWaiting = true;
                    await new Promise(resolve => { window.releaseSave = resolve; });
                }
            }
            return original(...args);
        };
    }""")
    field.fill("First autosave")
    page.wait_for_function("window.saveWaiting === true")
    field.fill("Newest edit wins")
    page.evaluate("window.releaseSave()")
    page.get_by_role("combobox", name="Projekt wechseln", exact=True).select_option(b)
    playwright.expect(page.get_by_role("heading", name="Browser B", exact=True)).to_be_visible()
    assert title(client, a) == "Newest edit wins"
    assert title(client, b) == "Browser B"
    assert page.evaluate("window.legendWrites") == ["First autosave", "Newest edit wins"]


def test_copy_contains_the_edit_that_was_pending_when_copy_was_requested(editor):
    page, field, client, (a, b) = editor
    field.fill("Include me in the copy")
    page.once("dialog", lambda dialog: dialog.accept("Browser copy"))
    page.locator("summary").filter(has_text="Projektaktionen").click()
    page.get_by_role("button", name="Projekt duplizieren", exact=True).click()
    playwright.expect(page.get_by_role("heading", name="Browser copy", exact=True)).to_be_visible(timeout=15000)
    assert title(client, a) == "Include me in the copy"
    assert title(client, "Browser copy") == "Include me in the copy"


def test_close_warning_only_appears_while_the_document_is_unsaved(editor):
    page, field, client, (a, b) = editor

    def closing_is_blocked():
        return page.evaluate("!window.dispatchEvent(new Event('beforeunload', { cancelable: true }))")

    assert not closing_is_blocked()
    field.fill("Not saved yet")
    assert closing_is_blocked()
    with page.expect_response(lambda response: response.request.method == "PUT" and LEGEND_URL.search(response.url)):
        page.get_by_role("button", name="Kategorien", exact=True).click()
    playwright.expect(page.get_by_role("button", name="Kategorien", exact=True)).to_have_class("tab active")
    assert not closing_is_blocked()
    assert title(client, a) == "Not saved yet"


def test_several_legends_are_edited_and_saved_separately(editor):
    page, field, client, (a, b) = editor
    field.fill("Hauptlegende")
    page.get_by_role("button", name="+ Neu", exact=True).click()
    page.get_by_label("Name", exact=True).fill("Brandmelder")
    page.get_by_role("radio", name="Leer", exact=True).check()
    page.get_by_role("button", name="Anlegen", exact=True).click()
    playwright.expect(page.get_by_label("Legende wählen").locator("option", has_text="Brandmelder")).to_have_count(1)
    page.get_by_role("button", name="T Titel", exact=True).click()
    playwright.expect(field).to_have_value("Brandmelder")
    field.fill("Brandmelder EG")
    page.get_by_label("Legende wählen").select_option(label="Legende")
    page.get_by_role("button", name="T Titel", exact=True).click()
    playwright.expect(field).to_have_value("Hauptlegende")
    items = client.get(f"/api/projects/{a}/legends").json()["items"]
    assert [i["name"] for i in items] == ["Legende", "Brandmelder"]
    second = client.get(f"/api/projects/{a}/legend?legend={items[1]['id']}").json()["legend"]
    assert second["doc"]["title"]["text"] == "Brandmelder EG"
    assert title(client, a) == "Hauptlegende"


def test_dragging_onto_an_empty_cell_places_the_entry_there(editor):
    page, field, client, (a, b) = editor
    doc = client.get(f"/api/projects/{a}/legend").json()["legend"]["doc"]
    entries = [{"id": f"e{k}", "kind": "text", "text": f"Eintrag {k}"} for k in range(4)]
    doc["style"]["columns"] = 3
    doc["blocks"] = [{"id": "blk", "title": "Test", "items": entries}]
    assert client.put(f"/api/projects/{a}/legend", json={"doc": doc}).status_code == 200
    # The open editor still shows the previous document. Leave and return so it
    # loads the legend just written; the legend switcher is a dropdown, not a tab.
    playwright.expect(page.get_by_label("Legende wählen")).to_be_visible()
    page.get_by_role("button", name="Gesamtliste", exact=False).click()
    page.get_by_role("button", name="Legende", exact=True).click()
    first = page.locator('[data-hit="item"][data-id="e0"]')
    last = page.locator('[data-hit="item"][data-id="e3"]')
    playwright.expect(last).to_be_visible()
    page.set_viewport_size({"width": 1600, "height": 1200})
    first.scroll_into_view_if_needed()
    src, ref = first.bounding_box(), last.bounding_box()
    # 4 entries in 3 columns: 2, 2 and an empty third column; aim at its second row
    tx, ty = ref["x"] + ref["width"] * 1.5, ref["y"] + ref["height"] / 2
    page.mouse.move(src["x"] + 10, src["y"] + src["height"] / 2)
    page.mouse.down()
    page.mouse.move(tx - 40, ty, steps=5)
    page.mouse.move(tx, ty, steps=5)
    # the entries glide: right after the preview arrives, a moved entry carries a transition
    page.wait_for_function("""() => [...document.querySelectorAll('g[data-entry]')]
        .some(g => (g.style.transition || '').includes('transform'))""", timeout=3000)
    page.wait_for_timeout(400)                 # live preview with the highlighted cell
    page.mouse.up()
    # right after the drop the entry is already at its new place (no jump back to the old one)
    page.wait_for_timeout(60)
    early = first.bounding_box()
    page.wait_for_timeout(1500)                # autosave
    late = first.bounding_box()
    assert abs(early["x"] - late["x"]) < 2 and abs(early["y"] - late["y"]) < 2
    items = client.get(f"/api/projects/{a}/legend").json()["legend"]["doc"]["blocks"][0]["items"]
    assert [it["kind"] == "gap" and "_" or it["id"] for it in items] == ["_", "e1", "e2", "e3", "_", "e0"]


def test_two_entries_are_combined_with_ctrl_click_and_split_again(editor):
    page, _field, client, (a, _b) = editor
    doc = client.get(f"/api/projects/{a}/legend").json()["legend"]["doc"]
    symbols = [it for b in doc["blocks"] for it in b["items"] if it["kind"] == "symbol"][:2]
    assert len(symbols) == 2
    for k, it in enumerate(symbols):
        it["id"], it["text"] = f"c{k}", ["Decke", "Wand"][k]
    doc["blocks"] = [{"id": "blk", "title": "Test", "items": symbols}]
    assert client.put(f"/api/projects/{a}/legend", json={"doc": doc}).status_code == 200
    playwright.expect(page.get_by_label("Legende wählen")).to_be_visible()
    page.get_by_role("button", name="Gesamtliste", exact=False).click()
    page.get_by_role("button", name="Legende", exact=True).click()
    page.set_viewport_size({"width": 1600, "height": 1200})
    page.locator('[data-hit="item"][data-id="c0"]').click()
    page.locator('[data-hit="item"][data-id="c1"]').click(modifiers=["Control"])
    combine = page.get_by_role("button", name="Kombinieren", exact=True)
    playwright.expect(combine).to_be_visible()
    with page.expect_response(LEGEND_URL) as saved:
        combine.click()
    assert saved.value.ok
    playwright.expect(page.locator("svg text", has_text="Decke / Wand")).to_be_visible()
    page.get_by_role("tab", name="Text 2 / Symbol 2").click()
    playwright.expect(page.get_by_label("Grösse Symbol 2")).to_be_visible()
    items = client.get(f"/api/projects/{a}/legend").json()["legend"]["doc"]["blocks"][0]["items"]
    assert [it["id"] for it in items] == ["c0"] and items[0]["parts"][0]["text"] == "Wand"
    with page.expect_response(LEGEND_URL) as saved:
        page.get_by_role("button", name="Trennen", exact=True).click()
    assert saved.value.ok
    items = client.get(f"/api/projects/{a}/legend").json()["legend"]["doc"]["blocks"][0]["items"]
    assert [it["text"] for it in items] == ["Decke", "Wand"] and not items[0].get("parts")


def test_the_admin_list_is_visible_and_locks_after_the_first_name(env, monkeypatch):
    """Everyone sees the same star list. An empty list stays open; afterwards only admins edit it."""
    from nova_legend import config

    client, _tmp = env
    ui = Path(__file__).resolve().parents[2] / "ui" / "dist"
    if not (ui / "index.html").is_file():
        pytest.skip("Build the UI with npm run build before browser tests")
    me = config.current_user()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(client.app.state.nova, ui_dir=ui), log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("Browser test API did not start")
        time.sleep(0.02)
    shots = Path("/opt/cursor/artifacts/screenshots")
    shots.mkdir(parents=True, exist_ok=True)
    try:
        with playwright.sync_playwright() as pw:
            browser = launch_chromium(pw)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(f"http://127.0.0.1:{port}")
            page.get_by_role("button", name="Einstellungen", exact=True).click()
            playwright.expect(page.get_by_role("heading", name="Legende Allgemein", exact=True)).to_be_visible()
            playwright.expect(page.get_by_role("heading", name="Admin", exact=True)).to_be_visible()
            playwright.expect(page.get_by_text("Zeilen der Legende Allgemein", exact=True)).to_be_visible()
            playwright.expect(page.get_by_text("Windows-Name dieses Computers", exact=False)).to_be_visible()
            assert page.get_by_text("Legende der Firma", exact=True).count() == 0
            assert page.get_by_text("NovaFirma12").count() == 0
            playwright.expect(page.locator(".card", has=page.get_by_role("heading", name="Benutzerschablonen")).locator(".stencil-read")).to_be_visible()
            playwright.expect(page.get_by_label("Update-Kanal")).to_be_visible()
            playwright.expect(page.get_by_text("Offen für alle", exact=True)).to_be_visible()
            playwright.expect(page.get_by_text("jeder darf ändern", exact=False)).to_be_visible()
            page.locator(".card", has=page.get_by_role("heading", name="Legende Allgemein", exact=True)).screenshot(
                path=str(shots / "legende-allgemein.png"))
            page.locator(".admin-box").screenshot(path=str(shots / "admin-offen.png"))
            assert client.put("/api/company/legend", json={"admins": [me, "marco"]}).status_code == 200
            page.reload()
            page.get_by_role("button", name="Einstellungen", exact=True).click()
            playwright.expect(page.get_by_label("Update-Kanal")).to_be_visible()
            playwright.expect(page.get_by_text("Du bist Admin", exact=True)).to_be_visible()
            playwright.expect(page.get_by_text("Nur Admins können weitere Namen", exact=False)).to_be_visible()
            playwright.expect(page.locator(".admin-list")).to_contain_text(me)
            playwright.expect(page.locator(".admin-list")).to_contain_text("marco")
            assert page.locator(".admin-list .star").count() == 2
            page.locator("section.admin-box").screenshot(path=str(shots / "admin-du.png"))
            monkeypatch.setattr(config, "current_user", lambda: "gast")
            page.reload()
            page.get_by_role("button", name="Einstellungen", exact=True).click()
            playwright.expect(page.get_by_label("Update-Kanal")).to_have_count(0)
            playwright.expect(page.get_by_text("Nicht Admin", exact=True)).to_be_visible()
            playwright.expect(page.get_by_text("Die Liste ist gesperrt", exact=False)).to_be_visible()
            playwright.expect(page.get_by_label("Admin-Liste")).to_be_disabled()
            page.locator(".card", has=page.locator(".admin-title")).screenshot(path=str(shots / "admin-gesperrt.png"))
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
