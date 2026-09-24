# mview

> **Fast, fully offline GitHub-style Markdown viewer CLI with live reload.**

`mview` renders local markdown files exactly the way GitHub renders `README.md`, opens the preview in your default browser, and works **100% offline with zero CDN dependencies**.

---

## Features

- **GitHub Flavored Markdown (GFM)**: Built on [`markdown-it-py`](https://github.com/executablebooks/markdown-it-py) for strict CommonMark and GFM compliance.
- **100% Offline (Zero CDN calls)**: All CSS stylesheets and JavaScript bundles are vendored locally inside the package:
  - `github-markdown-css` (with auto-detecting light & dark modes via `prefers-color-scheme`)
  - `highlight.js` (11.12.0) with GitHub Light & Dark themes
  - `mermaid.js` (10.9.8) for native diagram generation
- **Headings with GitHub Anchors**: Automatic GitHub-style slugification (downcased, stripped punctuation, duplicate-handling `-1`, `-2`) and hover anchor link icons (`.octicon-link`).
- **Mermaid Diagrams**: Code fences with ` ```mermaid ` automatically render as interactive SVG diagrams (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, `gitGraph`, etc.).
- **Graceful Error Handling**: Malformed Mermaid blocks display clear inline error diagnostics without crashing or breaking other diagrams.
- **Task Lists & Tables**: Checkboxes (`- [ ]` / `- [x]`) and tables styled identically to GitHub READMEs.
- **Footnotes & Strikethrough**: Footnote jump references (`[^1]`), backreferences (`↩︎`), and strikethrough (`~~text~~`).
- **GitHub Alerts**: Official callout containers (`> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`) with Octicon icons.
- **Relative Image Resolution**: Local relative image paths (`images/diagram.png`) resolve relative to the markdown file. In static preview mode, local images are automatically converted to inline Base64 data URIs so they load cleanly across all modern browsers without `file://` security blocks.
- **Emoji Shortcodes**: Support for `:rocket:`, `:sparkles:`, `:tada:`, `:white_check_mark:`, and hundreds more.
- **Live-Reload Watch Mode (`--watch`)**: Starts a lightweight local HTTP server and file watcher (`watchdog`). Saves in your text editor trigger instantaneous browser refreshes via Server-Sent Events (SSE).
- **Lightweight & Cross-Platform**: No heavy browser engines or Electron wrappers. Opens directly in your operating system's existing default browser.

---

## Installation

### 1. Requirements
- Python 3.8 or higher
- `pip`

### 2. Global Installation (Recommended)

From the root of this repository:

```bash
# Install as an editable package for global CLI access
pip install -e .

# Or standard global installation
pip install .
```

Alternatively, you can use [`pipx`](https://pypa.github.io/pipx/) to install into an isolated global environment:

```bash
pipx install .
```

### 3. Verifying PATH Configuration

After installation, verify that the `mview` command is accessible from anywhere in your terminal:

```bash
mview --version
```

#### If `mview` is not recognized on Windows:
Ensure your Python Scripts directory is on your system `PATH`:
- Standard Python: `C:\Users\<Username>\AppData\Local\Programs\Python\Python311\Scripts`
- Pyenv Win: `C:\Users\<Username>\.pyenv\pyenv-win\bin` and `...\shims`
- User site-packages: `C:\Users\<Username>\AppData\Roaming\Python\Python311\Scripts`

To add Python Scripts to your user `PATH` on Windows (PowerShell):
```powershell
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";$((python -c 'import site; print(site.USER_BASE)') + '\Scripts')",
    "User"
)
```

#### On Linux / macOS:
Ensure `~/.local/bin` is in your `PATH` (typically inside `~/.bashrc` or `~/.zshrc`):
```bash
export PATH="$HOME/.local/bin:$PATH"
```

---

## Usage

### Preview a Markdown File

```bash
mview README.md
```
- Converts `README.md` to GitHub-styled HTML with vendored assets inlined.
- Saves to a temporary HTML file and opens it in your default browser.
- Exits immediately after opening.

### Live-Reload on Save (`--watch`)

```bash
mview README.md --watch
# or shorthand:
mview README.md -w
```
- Starts a local HTTP server and file watcher.
- Opens your browser to `http://127.0.0.1:<port>/`.
- Whenever you save `README.md` in your editor, your browser tab reloads within milliseconds.
- Press `Ctrl+C` to terminate the server.

### Browser Selection

By default, `mview` opens in your system's default browser. You can explicitly choose which browser to launch using `--browser` or direct shorthand flags:

```bash
# Specific browser via shorthand flags
mview README.md --edge
mview README.md --chrome
mview README.md --firefox
mview README.md --brave

# Or via --browser / -b parameter
mview README.md -b brave
mview README.md --browser firefox --watch
```

Supported browsers: `brave`, `chrome`, `edge`, `firefox`, `opera`, `safari`, `vivaldi`.

### Options & Flags

```text
usage: mview [-h] [-w] [-b NAME] [-p PORT] [--no-browser] [-v] [file]

Render a local markdown file exactly like GitHub README.md, fully offline, and open in browser.

positional arguments:
  file                  Path to the markdown file (.md) to preview.

options:
  -h, --help            show this help message and exit
  -w, --watch           Watch file for changes and auto-reload the browser on save.
  -b NAME, --browser NAME
                        Browser to open the preview in (brave, chrome, edge,
                        firefox, opera, safari, vivaldi). Default: system
                        default browser.
                        Shorthand flags also supported: --edge, --chrome,
                        --firefox, --brave, --opera, --vivaldi.
  -p PORT, --port PORT  Port to use for the live-reload HTTP server (default: auto free port starting at 8000).
  --no-browser          Do not open the default browser automatically (useful in scripts or tests).
  -v, --version         show program's version number and exit
```

---

## Showcase Sample

A comprehensive sample document showcasing all features is provided in [`sample.md`](file:///d:/Development/MView/sample.md):

```bash
# Static preview
mview sample.md

# Live reload preview
mview sample.md --watch
```

Features demonstrated in `sample.md`:
- Task list items with interactive checkboxes
- GFM tables with column alignment
- Multi-language syntax highlighting (Python, TypeScript, Rust)
- Mermaid flowcharts, sequence diagrams, and state diagrams
- Graceful inline handling for malformed Mermaid diagrams
- Relative local images (`sample_images/badge.svg`) via markdown and HTML tags
- GitHub callout alerts (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`)
- Footnotes with bidirectional jumping
- Emojis (`:rocket:`, `:tada:`, `:sparkles:`, etc.)

---

## Project Architecture

The codebase is cleanly organized with separation of concerns:

```
MView/
├── pyproject.toml              # Build & entry point configuration (mview = mview.cli:main)
├── README.md                   # Documentation and usage guide
├── sample.md                   # Feature showcase markdown file
├── sample_images/              # Local test assets
│   └── badge.svg
├── mview/
│   ├── __init__.py             # Package metadata
│   ├── cli.py                  # CLI argument parsing, input validation, execution dispatcher
│   ├── parser.py               # markdown-it parser, GFM plugins, slugger, anchors, alerts, emojis
│   ├── renderer.py             # Custom fence rule (mermaid vs code), relative image resolver
│   ├── template.py             # Self-contained HTML assembly, inlined CSS/JS, live-reload script
│   ├── watcher.py              # File watcher (watchdog), ThreadingHTTPServer, SSE reload broadcast
│   └── assets/                 # Vendored offline assets (no CDN runtime dependency)
│       ├── github-markdown.css
│       ├── highlight.min.js
│       ├── highlight-github.min.css
│       ├── highlight-github-dark.min.css
│       └── mermaid.min.js
└── tests/
    ├── test_cli.py             # CLI flags, errors, and static generation tests
    ├── test_parser.py          # Slugification, anchors, tables, tasks, footnotes, alerts tests
    ├── test_renderer.py        # Mermaid fences, code fences, image resolution tests
    ├── test_template.py        # Offline asset bundling and HTML structure tests
    └── test_watcher.py         # Watch manager debouncing and HTTP server endpoint tests
```

---

## Running the Test Suite

Run the automated test suite with `pytest`:

```bash
python -m pytest
```

All 28 tests cover CLI validation, parser extensions, renderer rules, image resolution, template generation, and live reload server behavior.
