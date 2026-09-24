"""Tests for the watch manager and live reload HTTP server."""

import json
from pathlib import Path
import threading
import time
import urllib.request

from mview.watcher import WatchManager, WatchServerHandler, find_free_port
import http.server


def test_find_free_port():
    port = find_free_port(9100)
    assert port >= 9100


def test_watch_manager_debounce(tmp_path: Path):
    md_file = tmp_path / "watch_test.md"
    md_file.write_text("# Initial", encoding="utf-8")

    manager = WatchManager(md_file)
    q = manager.register_client()

    initial_version = manager.version
    manager.on_file_event()
    time.sleep(0.2)  # Wait for 0.1s debounce

    assert manager.version != initial_version
    msg = q.get_nowait()
    assert msg == "reload"

    manager.unregister_client(q)


def test_watch_server_endpoints(tmp_path: Path):
    md_file = tmp_path / "index.md"
    md_file.write_text("# Live Test Content", encoding="utf-8")

    # Also create a static asset
    img_file = tmp_path / "test.png"
    img_file.write_bytes(b"dummy-png-data")

    port = find_free_port(9200)
    manager = WatchManager(md_file)

    handler_class = type(
        "TestWatchServerHandler",
        (WatchServerHandler,),
        {"manager": manager, "port": port},
    )

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_class)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        # Test GET /
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            assert resp.status == 200
            content = resp.read().decode("utf-8")
            assert "Live Test Content" in content
            assert "Live Reload" in content

        # Test GET /__mview_status__
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/__mview_status__") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "version" in data

        # Test static file serving
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/test.png") as resp:
            assert resp.status == 200
            assert resp.read() == b"dummy-png-data"

    finally:
        server.shutdown()
        server.server_close()
