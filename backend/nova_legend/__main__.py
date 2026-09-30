"""Start NOVA-Legenden.

    python -m nova_legend            own window (Windows: Edge WebView2), else browser
    python -m nova_legend --browser  always open the default browser
    python -m nova_legend --server   server only (development)

The server listens on 127.0.0.1 only, so nothing is reachable from the
network.
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser

from . import config


def free_port(preferred: int = 8765) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("Kein freier Port gefunden")


def wait_until_up(url: str, timeout: float = 60.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url + "/api/status", timeout=2):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def setup_logging() -> None:
    log_file = config.local_home() / "nova-legenden.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8")]
        + ([logging.StreamHandler()] if sys.stderr else []),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nova_legend")
    parser.add_argument("--browser", action="store_true", help="im Standardbrowser öffnen")
    parser.add_argument("--server", action="store_true", help="nur Server starten")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    setup_logging()
    log = logging.getLogger("nova_legend")

    import uvicorn

    from .api.app import create_app

    port = free_port(args.port)
    url = f"http://127.0.0.1:{port}"
    try:
        app = create_app()
    except Exception:  # noqa: BLE001 - show any start error in the log
        log.error("Start fehlgeschlagen:\n%s", traceback.format_exc())
        raise
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                           log_config=None, log_level="warning"))
    if args.server:
        log.info("Server läuft auf %s", url)
        server.run()
        return 0

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    if not wait_until_up(url):
        log.error("Server startet nicht")
        return 1
    log.info("Oberfläche: %s", url)

    if not args.browser:
        try:
            import webview  # pywebview, installed in the Windows build

            webview.settings["ALLOW_DOWNLOADS"] = True   # project export (ZIP)

            window = webview.create_window(f"NOVA-Legenden {config.APP_VERSION}", url,
                                           width=1400, height=900, min_size=(900, 600))
            app.state.shutdown = window.destroy  # used by the program update
            webview.start()
            server.should_exit = True
            return 0
        except Exception:  # noqa: BLE001 - fall back to the browser
            log.warning("Eigenes Fenster nicht möglich, öffne Browser:\n%s", traceback.format_exc())

    app.state.shutdown = lambda: setattr(server, "should_exit", True)
    webbrowser.open(url)
    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.should_exit = True
    return 0


if __name__ == "__main__":
    sys.exit(main())
