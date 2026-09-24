"""HTML template generation and offline asset bundling for mview."""

from __future__ import annotations

import functools
import html
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"


# Lazy-load individual assets so we never read 3MB of mermaid.js when it's not needed.
@functools.lru_cache(maxsize=1)
def _load_css_assets() -> dict[str, str]:
    return {
        "github_markdown_css": (ASSETS_DIR / "github-markdown.css").read_text(encoding="utf-8"),
        "highlight_github_css": (ASSETS_DIR / "highlight-github.min.css").read_text(encoding="utf-8"),
        "highlight_github_dark_css": (ASSETS_DIR / "highlight-github-dark.min.css").read_text(encoding="utf-8"),
    }


@functools.lru_cache(maxsize=1)
def _load_highlight_js() -> str:
    return (ASSETS_DIR / "highlight.min.js").read_text(encoding="utf-8")


@functools.lru_cache(maxsize=1)
def _load_mermaid_js() -> str:
    return (ASSETS_DIR / "mermaid.min.js").read_text(encoding="utf-8")


def load_assets() -> dict[str, str]:
    """Load all bundled offline assets (kept for test compatibility)."""
    css = _load_css_assets()
    return {
        **css,
        "highlight_min_js": _load_highlight_js(),
        "mermaid_min_js": _load_mermaid_js(),
    }


DOCUMENT_ICON_SVG = (
    '<svg class="octicon octicon-file" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true">'
    '<path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.75.75V4.25c0 .138.112.25.25.25h2.5Z"></path>'
    '</svg>'
)


def _detect_features(content_html: str) -> dict[str, bool]:
    """Scan the rendered HTML to determine which heavy assets are actually needed."""
    return {
        "has_code_blocks": '<code class="language-' in content_html or "<code>" in content_html,
        "has_mermaid": '<pre class="mermaid">' in content_html,
    }


def render_html_page(
    content_html: str,
    filename: str,
    base_dir: Path,
    watch_mode: bool = False,
    port: int | None = None,
) -> str:
    """Generate a complete, fully offline, self-contained HTML page.

    Heavy JS assets (highlight.js ~126KB, mermaid.js ~3.2MB) are only included
    when the rendered markdown actually contains code blocks or mermaid diagrams.
    In watch mode they are always included since content can change on reload.
    """
    css_assets = _load_css_assets()
    features = _detect_features(content_html)

    need_highlight = watch_mode or features["has_code_blocks"]
    need_mermaid = watch_mode or features["has_mermaid"]

    base_tag = ""
    if not watch_mode:
        # Provide base href fallback for any remaining relative links
        base_dir_uri = base_dir.resolve().as_uri()
        base_tag = f'<base href="{base_dir_uri}/">'

    # Watch script if live-reload enabled
    watch_script = ""
    if watch_mode:
        watch_script = """
    // Live reload integration
    function initLiveReload() {
      if (!window.EventSource) {
        let lastVer = null;
        setInterval(async () => {
          try {
            const res = await fetch('/__mview_status__');
            const data = await res.json();
            if (lastVer === null) lastVer = data.version;
            else if (data.version !== lastVer) location.reload();
          } catch (e) {}
        }, 400);
        return;
      }
      const es = new EventSource('/__mview_events__');
      es.onmessage = function(e) {
        if (e.data === 'reload') {
          location.reload();
        }
      };
      es.onerror = function() {
        // Will auto-reconnect
      };
    }
    initLiveReload();
"""

    badge_text = f"Live Reload (:{port})" if (watch_mode and port) else "Offline Preview"
    safe_filename = html.escape(filename)

    # Build highlight.js CSS conditionally
    highlight_css_block = ""
    if need_highlight:
        highlight_css_block = f"""
  <style>
    /* Vendored highlight.js themes with dark/light auto switching */
    @media (prefers-color-scheme: light) {{
      {css_assets['highlight_github_css']}
    }}
    @media (prefers-color-scheme: dark) {{
      {css_assets['highlight_github_dark_css']}
    }}
  </style>"""

    # Build JS blocks conditionally
    highlight_js_block = ""
    if need_highlight:
        highlight_js_block = f"""
  <script>
    // Vendored highlight.js
    {_load_highlight_js()}
  </script>"""

    mermaid_js_block = ""
    if need_mermaid:
        mermaid_js_block = f"""
  <script>
    // Vendored mermaid.js
    {_load_mermaid_js()}
  </script>"""

    # Build initialization script
    init_parts = []
    if need_highlight:
        init_parts.append("""
      // Initialize highlight.js
      if (typeof hljs !== 'undefined') {
        hljs.highlightAll();
      }""")

    if need_mermaid:
        init_parts.append("""
      // Initialize and render Mermaid diagrams
      if (typeof mermaid !== 'undefined') {
        const isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        mermaid.initialize({
          startOnLoad: false,
          theme: isDarkMode ? 'dark' : 'default',
          securityLevel: 'loose',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'
        });

        const mermaidBlocks = Array.from(document.querySelectorAll('pre.mermaid'));
        mermaidBlocks.forEach(async (el, index) => {
          const rawCode = el.textContent.trim();
          try {
            const id = 'mermaid-diag-' + index;
            const { svg } = await mermaid.render(id, rawCode);
            const container = document.createElement('div');
            container.className = 'mermaid-rendered';
            container.innerHTML = svg;
            el.replaceWith(container);
          } catch (err) {
            console.error('Mermaid render error for block ' + index + ':', err);
            const errDiv = document.createElement('div');
            errDiv.className = 'mermaid-error';
            errDiv.textContent = 'Mermaid diagram error:\\n' + (err.message || String(err));
            el.replaceWith(errDiv);
          }
        });

        // Listen for OS theme switch and reload to re-theme diagrams
        if (window.matchMedia) {
          window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            location.reload();
          });
        }
      }""")

    if watch_mode:
        init_parts.append(watch_script)

    init_script = "\n".join(init_parts)

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_filename} - mview</title>
  {base_tag}
  <style>
    /* Vendored github-markdown-css */
    {css_assets['github_markdown_css']}
  </style>
  {highlight_css_block}
  <style>
    /* Global page layout matching GitHub style */
    :root {{
      color-scheme: light dark;
      --mview-bg: #f6f8fa;
      --mview-card-bg: #ffffff;
      --mview-border: #d1d9e0;
      --mview-text: #1f2328;
      --mview-header-bg: #f6f8fa;
      --mview-badge-bg: #e1e4e8;
      --mview-badge-text: #57606a;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --mview-bg: #010409;
        --mview-card-bg: #0d1117;
        --mview-border: #30363d;
        --mview-text: #f0f6fc;
        --mview-header-bg: #161b22;
        --mview-badge-bg: #21262d;
        --mview-badge-text: #8b949e;
      }}
    }}

    body {{
      margin: 0;
      padding: 0;
      background-color: var(--mview-bg);
      color: var(--mview-text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
    }}

    .mview-wrapper {{
      max-width: 1012px;
      margin: 24px auto 48px auto;
      padding: 0 16px;
    }}

    .mview-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 16px;
      background-color: var(--mview-header-bg);
      border: 1px solid var(--mview-border);
      border-bottom: none;
      border-top-left-radius: 6px;
      border-top-right-radius: 6px;
      font-size: 14px;
      font-weight: 600;
    }}

    .mview-header-left {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .mview-header-left svg {{
      fill: currentColor;
      opacity: 0.8;
    }}

    .mview-badge {{
      font-size: 12px;
      font-weight: 500;
      padding: 2px 8px;
      border-radius: 12px;
      background-color: var(--mview-badge-bg);
      color: var(--mview-badge-text);
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}

    .mview-badge-dot {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background-color: {'#2da44e' if watch_mode else '#8c959f'};
      display: inline-block;
    }}

    .markdown-body {{
      box-sizing: border-box;
      min-width: 200px;
      max-width: 100%;
      margin: 0;
      padding: 32px 36px;
      border: 1px solid var(--mview-border);
      border-bottom-left-radius: 6px;
      border-bottom-right-radius: 6px;
      background-color: var(--mview-card-bg);
    }}

    /* Pre and code block overrides for clean highlight.js integration */
    .markdown-body pre code.hljs {{
      background: transparent;
      padding: 0;
    }}

    /* Mermaid diagrams container and inline graceful error styles */
    .mermaid-rendered {{
      display: flex;
      justify-content: center;
      margin: 20px 0;
      overflow-x: auto;
    }}

    .mermaid-rendered svg {{
      max-width: 100%;
      height: auto;
    }}

    .mermaid-error {{
      padding: 12px 16px;
      margin: 16px 0;
      border: 1px solid #f85149;
      border-radius: 6px;
      background-color: rgba(248, 81, 73, 0.1);
      color: #f85149;
      font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace;
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
    }}

    @media (max-width: 767px) {{
      .mview-wrapper {{
        margin: 0;
        padding: 0;
      }}
      .mview-header {{
        border-radius: 0;
        border-left: none;
        border-right: none;
        border-top: none;
      }}
      .markdown-body {{
        border: none;
        border-radius: 0;
        padding: 20px 16px;
      }}
    }}
  </style>
</head>
<body>
  <div class="mview-wrapper">
    <header class="mview-header">
      <div class="mview-header-left">
        {DOCUMENT_ICON_SVG}
        <span>{safe_filename}</span>
      </div>
      <div class="mview-badge">
        <span class="mview-badge-dot"></span>
        <span>{badge_text}</span>
      </div>
    </header>
    <main class="markdown-body">
      {content_html}
    </main>
  </div>

  {highlight_js_block}
  {mermaid_js_block}
  <script>
    (function() {{
      {init_script}
    }})();
  </script>
</body>
</html>"""
    return page_html
