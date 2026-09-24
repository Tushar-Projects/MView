"""File watcher and live-reload HTTP server for mview."""

from __future__ import annotations

import http.server
import json
import mimetypes
from pathlib import Path
import queue
import socket
import sys
import threading
import time
from typing import TYPE_CHECKING, Set
import urllib.parse

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from mview.parser import create_markdown_parser
from mview.renderer import postprocess_html_images, setup_renderer
from mview.template import render_html_page


def find_free_port(preferred_port: int = 8000) -> int:
    """Find a free TCP port starting from preferred_port."""
    for port in range(preferred_port, preferred_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    # Let the OS pick an available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class WatchManager:
    """Coordinates file watching, state versioning, and client event notifications."""

    def __init__(self, target_file: Path) -> None:
        self.target_file = target_file.resolve()
        self.base_dir = self.target_file.parent
        self.version = int(time.time() * 1000)
        self.clients_lock = threading.Lock()
        self.clients: Set[queue.Queue[str]] = set()
        self._debounce_timer: threading.Timer | None = None
        self._timer_lock = threading.Lock()

    def register_client(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue()
        with self.clients_lock:
            self.clients.add(q)
        return q

    def unregister_client(self, q: queue.Queue[str]) -> None:
        with self.clients_lock:
            self.clients.discard(q)

    def trigger_reload(self) -> None:
        self.version = int(time.time() * 1000)
        with self.clients_lock:
            for q in list(self.clients):
                try:
                    q.put_nowait("reload")
                except Exception:
                    pass

    def on_file_event(self) -> None:
        with self._timer_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(0.1, self.trigger_reload)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def render_current_page(self, port: int) -> str:
        """Render the current markdown file to full HTML."""
        try:
            content = self.target_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = self.target_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            content = f"# Error reading file\n\n`{html.escape(str(e))}`"

        parser = create_markdown_parser()
        setup_renderer(parser, self.base_dir, watch_mode=True)
        body_html = parser.render(content)
        body_html = postprocess_html_images(body_html, self.base_dir, watch_mode=True)

        return render_html_page(
            content_html=body_html,
            filename=self.target_file.name,
            base_dir=self.base_dir,
            watch_mode=True,
            port=port,
        )


class MarkdownFileEventHandler(FileSystemEventHandler):
    """Watches for changes specifically to the targeted markdown file."""

    def __init__(self, manager: WatchManager) -> None:
        super().__init__()
        self.manager = manager
        self.target_path_str = str(manager.target_file)

    def on_any_event(self, event: FileSystemEvent) -> None:
        # Check both src_path and dest_path (for move/rename events)
        src = getattr(event, "src_path", "")
        dest = getattr(event, "dest_path", "")
        if src == self.target_path_str or dest == self.target_path_str:
            self.manager.on_file_event()


class WatchServerHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP Request handler for serving the live preview and assets."""

    manager: WatchManager
    port: int

    def log_message(self, format: str, *args: object) -> None:
        # Suppress routine request logging to keep CLI output clean
        pass

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/", "/index.html"):
            self.handle_index()
        elif path == "/__mview_events__":
            self.handle_events()
        elif path == "/__mview_status__":
            self.handle_status()
        elif path == "/_file":
            self.handle_direct_file(parsed_url.query)
        else:
            self.handle_static_file(path)

    def handle_index(self) -> None:
        html_page = self.manager.render_current_page(self.port)
        encoded = html_page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(encoded)

    def handle_status(self) -> None:
        data = json.dumps({"version": self.manager.version}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def handle_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q = self.manager.register_client()
        try:
            # Send initial connected ping
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()

            while True:
                try:
                    msg = q.get(timeout=15.0)
                    self.wfile.write(f"data: {msg}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # Keep-alive comment
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            self.manager.unregister_client(q)

    def handle_direct_file(self, query_string: str) -> None:
        query_params = urllib.parse.parse_qs(query_string)
        target_path_param = query_params.get("path", [""])[0]
        if not target_path_param:
            self.send_error(400, "Missing path parameter")
            return

        file_path = Path(urllib.parse.unquote(target_path_param)).resolve()
        if not file_path.is_file():
            self.send_error(404, "File not found")
            return

        self.serve_file_content(file_path)

    def handle_static_file(self, url_path: str) -> None:
        # Attempt to resolve path relative to base_dir
        clean_rel = url_path.lstrip("/")
        unquoted = urllib.parse.unquote(clean_rel)
        file_path = (self.manager.base_dir / unquoted).resolve()

        if file_path.is_file():
            self.serve_file_content(file_path)
        else:
            self.send_error(404, "File not found")

    def serve_file_content(self, file_path: Path) -> None:
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            if file_path.suffix.lower() == ".svg":
                mime_type = "image/svg+xml"
            else:
                mime_type = "application/octet-stream"

        try:
            file_bytes = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(file_bytes)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(file_bytes)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")


def start_watch_server(
    target_file: Path,
    port: int | None = None,
    open_browser: bool = True,
    browser: str | None = None,
) -> None:
    """Start the watchdog file watcher and local HTTP live-reload server."""
    if port is None or port == 0:
        port = find_free_port(8000)

    manager = WatchManager(target_file)

    handler_class = type(
        "ConfiguredWatchServerHandler",
        (WatchServerHandler,),
        {"manager": manager, "port": port},
    )

    # Use ThreadingHTTPServer so SSE streams don't block other requests
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler_class)
    server.daemon_threads = True

    # Setup watchdog observer
    event_handler = MarkdownFileEventHandler(manager)
    observer = Observer()
    observer.schedule(event_handler, path=str(manager.base_dir), recursive=False)
    observer.start()

    url = f"http://127.0.0.1:{port}/"
    print(f"[mview] Watching '{target_file.name}' for changes...")
    print(f"[mview] Live preview available at: {url}")
    print("[mview] Press Ctrl+C to stop.")

    if open_browser:
        from mview.cli import open_file_in_browser

        # For HTTP URLs, create a tiny temp redirect or just launch the browser directly
        import subprocess as _sp

        if browser:
            browser_lower = browser.lower().strip()
            if sys.platform == "win32":
                from mview.cli import _find_browser_exe_win

                exe = _find_browser_exe_win(browser_lower)
                if exe:
                    _sp.Popen([exe, url], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                else:
                    sys.stderr.write(f"Warning: Browser '{browser}' not found, using default.\n")
                    _sp.Popen(["cmd", "/c", "start", "", url], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            elif sys.platform == "darwin":
                from mview.cli import _MAC_BROWSER_APPS

                app_name = _MAC_BROWSER_APPS.get(browser_lower)
                if app_name:
                    _sp.Popen(["open", "-a", app_name, url], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                else:
                    _sp.Popen(["open", url], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            else:
                import shutil

                from mview.cli import _LINUX_BROWSER_CMDS

                launched = False
                for cmd in _LINUX_BROWSER_CMDS.get(browser_lower, [browser_lower]):
                    found = shutil.which(cmd)
                    if found:
                        _sp.Popen([found, url], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                        launched = True
                        break
                if not launched:
                    import webbrowser

                    webbrowser.open(url)
        else:
            if sys.platform == "win32":
                _sp.Popen(["cmd", "/c", "start", "", url], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            else:
                import webbrowser

                webbrowser.open(url)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[mview] Stopping watch server...")
    finally:
        observer.stop()
        observer.join(timeout=2.0)
        server.shutdown()
        server.server_close()
        print("[mview] Stopped.")
