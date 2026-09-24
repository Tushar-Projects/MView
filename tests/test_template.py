"""Tests for HTML template generation and offline asset bundling."""

from pathlib import Path
from mview.template import load_assets, render_html_page


def test_offline_assets_loaded():
    assets = load_assets()
    assert "github_markdown_css" in assets
    assert "highlight_github_css" in assets
    assert "highlight_github_dark_css" in assets
    assert "highlight_min_js" in assets
    assert "mermaid_min_js" in assets

    # Ensure assets have valid content
    assert len(assets["github_markdown_css"]) > 10000
    assert len(assets["highlight_min_js"]) > 50000
    assert len(assets["mermaid_min_js"]) > 1000000


def test_render_html_page_no_cdn():
    html_out = render_html_page(
        content_html="<h1>Test</h1>",
        filename="test.md",
        base_dir=Path("."),
        watch_mode=False,
    )

    # OFFLINE REQUIREMENT: Verify zero external CDN links in the HTML
    assert "cdn.jsdelivr.net" not in html_out
    assert "cdnjs.cloudflare.com" not in html_out
    assert "unpkg.com" not in html_out
    assert "https://" not in html_out.split("<style>")[0]  # No external links in head

    # Check required elements
    assert '<div class="mview-wrapper">' in html_out
    assert '<main class="markdown-body">' in html_out
    assert "test.md" in html_out
    assert "Offline Preview" in html_out


def test_render_html_page_with_code_includes_highlight():
    """When content has code blocks, highlight.js must be included."""
    html_out = render_html_page(
        content_html='<pre><code class="language-python">print(1)</code></pre>',
        filename="test.md",
        base_dir=Path("."),
        watch_mode=False,
    )
    assert "hljs.highlightAll()" in html_out
    assert len(html_out) > 100_000  # highlight.js is ~126KB


def test_render_html_page_without_code_skips_highlight():
    """When content has no code blocks, highlight.js should be skipped."""
    html_out = render_html_page(
        content_html="<h1>Test</h1><p>Hello</p>",
        filename="test.md",
        base_dir=Path("."),
        watch_mode=False,
    )
    assert "hljs.highlightAll()" not in html_out
    assert len(html_out) < 100_000  # Much smaller without JS


def test_render_html_page_with_mermaid_includes_mermaidjs():
    """When content has mermaid blocks, mermaid.js must be included."""
    html_out = render_html_page(
        content_html='<pre class="mermaid">graph TD\nA-->B</pre>',
        filename="test.md",
        base_dir=Path("."),
        watch_mode=False,
    )
    assert "mermaid.initialize" in html_out
    assert len(html_out) > 1_000_000  # mermaid.js is ~3.2MB


def test_render_html_page_without_mermaid_skips_mermaidjs():
    """When content has no mermaid blocks, mermaid.js should be skipped."""
    html_out = render_html_page(
        content_html="<h1>Test</h1><p>Hello</p>",
        filename="test.md",
        base_dir=Path("."),
        watch_mode=False,
    )
    assert "mermaid.initialize" not in html_out
    assert len(html_out) < 100_000


def test_render_html_page_watch_mode_includes_everything():
    """Watch mode always includes all assets since content can change on reload."""
    html_out = render_html_page(
        content_html="<h1>Test</h1>",
        filename="test.md",
        base_dir=Path("."),
        watch_mode=True,
        port=8765,
    )

    assert "Live Reload (:8765)" in html_out
    assert "initLiveReload" in html_out
    assert "/__mview_events__" in html_out
    assert "hljs.highlightAll()" in html_out
    assert "mermaid.initialize" in html_out
