"""CLI entry point for mview."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import webbrowser

from mview import __version__
from mview.parser import create_markdown_parser
from mview.renderer import postprocess_html_images, setup_renderer
from mview.template import render_html_page
from mview.watcher import start_watch_server

# Well-known browser executable locations on Windows.
# Each key maps to a list of candidate paths (checked in order).
_WIN_BROWSER_PATHS: dict[str, list[str]] = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
    "opera": [
        r"C:\Program Files\Opera\launcher.exe",
        r"C:\Program Files (x86)\Opera\launcher.exe",
    ],
    "vivaldi": [
        r"C:\Program Files\Vivaldi\Application\vivaldi.exe",
        r"C:\Program Files (x86)\Vivaldi\Application\vivaldi.exe",
    ],
}

# macOS application names (for `open -a`)
_MAC_BROWSER_APPS: dict[str, str] = {
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "firefox": "Firefox",
    "brave": "Brave Browser",
    "safari": "Safari",
    "opera": "Opera",
    "vivaldi": "Vivaldi",
}

# Linux executable names (looked up via PATH)
_LINUX_BROWSER_CMDS: dict[str, list[str]] = {
    "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    "edge": ["microsoft-edge", "microsoft-edge-stable"],
    "firefox": ["firefox"],
    "brave": ["brave-browser", "brave"],
    "opera": ["opera"],
    "vivaldi": ["vivaldi", "vivaldi-stable"],
}

SUPPORTED_BROWSERS = sorted(set(_WIN_BROWSER_PATHS) | set(_MAC_BROWSER_APPS) | {"safari"})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mview",
        description="Render a local markdown file exactly like GitHub README.md, fully offline, and open in browser.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the markdown file (.md) to preview.",
    )
    parser.add_argument(
        "-w",
        "--watch",
        action="store_true",
        help="Watch file for changes and auto-reload the browser on save.",
    )
    parser.add_argument(
        "-b",
        "--browser",
        metavar="NAME",
        default=None,
        help=f"Browser to open the preview in ({', '.join(SUPPORTED_BROWSERS)}). "
        "Default: system default browser.",
    )
    # Shorthand convenience flags — each is equivalent to --browser <name>
    for name in SUPPORTED_BROWSERS:
        parser.add_argument(
            f"--{name}",
            action="store_const",
            const=name,
            dest="browser",
            help=argparse.SUPPRESS,  # Keep --help clean; --browser documents them all
        )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=None,
        help="Port to use for the live-reload HTTP server (default: random free port starting at 8000).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the default browser automatically.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(argv)


def validate_file(file_arg: str | None) -> Path:
    """Validate that the argument points to an existing .md file."""
    if not file_arg:
        sys.stderr.write("Error: Missing markdown file argument.\n")
        sys.stderr.write("Usage: mview <file.md> [--watch]\n")
        sys.exit(1)

    path = Path(file_arg).resolve()

    if not path.exists():
        sys.stderr.write(f"Error: File not found: '{file_arg}'\n")
        sys.exit(1)

    if path.is_dir():
        sys.stderr.write(f"Error: '{file_arg}' is a directory, not a markdown file.\n")
        sys.exit(1)

    valid_extensions = {".md", ".markdown", ".mdown", ".mkd"}
    if path.suffix.lower() not in valid_extensions:
        sys.stderr.write(
            f"Error: '{file_arg}' is not a markdown file (expected extension: .md).\n"
        )
        sys.exit(1)

    return path


def _find_browser_exe_win(browser: str) -> str | None:
    """Find the executable path for a named browser on Windows."""
    import shutil

    candidates = _WIN_BROWSER_PATHS.get(browser, [])
    for path in candidates:
        if Path(path).is_file():
            return path

    # Fallback: try to find it on PATH
    for cmd in _LINUX_BROWSER_CMDS.get(browser, [browser]):
        found = shutil.which(cmd)
        if found:
            return found

    return None


def open_file_in_browser(file_path: Path, browser: str | None = None) -> None:
    """Open a local HTML file in a specific or the default browser."""
    target = str(file_path)

    # --- Specific browser requested ---
    if browser:
        browser = browser.lower().strip()

        if sys.platform == "win32":
            exe = _find_browser_exe_win(browser)
            if exe:
                subprocess.Popen(
                    [exe, target],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            # If not found, fall through to error

        elif sys.platform == "darwin":
            app_name = _MAC_BROWSER_APPS.get(browser)
            if app_name:
                subprocess.Popen(
                    ["open", "-a", app_name, target],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return

        else:  # Linux / other
            import shutil

            for cmd in _LINUX_BROWSER_CMDS.get(browser, [browser]):
                found = shutil.which(cmd)
                if found:
                    subprocess.Popen(
                        [found, target],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return

        sys.stderr.write(f"Warning: Browser '{browser}' not found, falling back to system default.\n")

    # --- System default browser ---
    if sys.platform == "win32":
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass

    webbrowser.open(file_path.as_uri())


def preview_static(target_file: Path, open_browser: bool = True, browser: str | None = None) -> Path:
    """Generate self-contained HTML for target_file, write to temp file, and open in browser."""
    try:
        content = target_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = target_file.read_text(encoding="utf-8", errors="replace")

    base_dir = target_file.parent
    parser = create_markdown_parser()
    setup_renderer(parser, base_dir, watch_mode=False)

    body_html = parser.render(content)
    body_html = postprocess_html_images(body_html, base_dir, watch_mode=False)

    full_html = render_html_page(
        content_html=body_html,
        filename=target_file.name,
        base_dir=base_dir,
        watch_mode=False,
    )

    # Use a descriptive prefix so the file is easily identifiable in the Temp directory
    clean_stem = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in target_file.stem)
    prefix = f"mview_{clean_stem[:30]}_"

    with tempfile.NamedTemporaryFile("w", prefix=prefix, suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(full_html)
        temp_path = Path(tf.name)

    print(f"[mview] Rendered: {target_file.name}")
    print(f"[mview] Preview:  {temp_path}")

    if open_browser:
        browser_label = browser or "default browser"
        open_file_in_browser(temp_path, browser=browser)
        print(f"[mview] Opened preview in {browser_label}.")

    return temp_path


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    target_file = validate_file(args.file)

    if args.watch:
        start_watch_server(
            target_file=target_file,
            port=args.port,
            open_browser=not args.no_browser,
            browser=args.browser,
        )
    else:
        preview_static(
            target_file=target_file,
            open_browser=not args.no_browser,
            browser=args.browser,
        )


if __name__ == "__main__":
    main()
