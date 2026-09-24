"""Tests for custom renderer rules, mermaid block detection, and image resolution."""

from pathlib import Path
import tempfile

from mview.parser import create_markdown_parser
from mview.renderer import postprocess_html_images, resolve_image_path, setup_renderer


def test_mermaid_fenced_blocks():
    parser = create_markdown_parser()
    setup_renderer(parser, Path("."))
    md = "```mermaid\ngraph TD\nA-->B\n```"
    html = parser.render(md)

    assert '<pre class="mermaid">' in html
    assert "graph TD" in html
    assert "A--&gt;B" in html


def test_code_fenced_blocks():
    parser = create_markdown_parser()
    setup_renderer(parser, Path("."))
    md = "```python\nprint('hello')\n```"
    html = parser.render(md)

    assert 'class="highlight highlight-source-python"' in html
    assert '<code class="language-python">' in html
    assert "print(&#x27;hello&#x27;)" in html or "print('hello')" in html


def test_relative_image_resolution_static(tmp_path: Path):
    # Create a dummy image file
    img_file = tmp_path / "test.svg"
    img_file.write_text("<svg></svg>", encoding="utf-8")

    resolved = resolve_image_path("test.svg", tmp_path, watch_mode=False)
    assert resolved.startswith("data:image/svg+xml;base64,")


def test_relative_image_resolution_watch(tmp_path: Path):
    img_file = tmp_path / "test.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    resolved = resolve_image_path("test.png", tmp_path, watch_mode=True)
    assert resolved.startswith("/_file?path=")


def test_external_image_resolution():
    url = "https://example.com/logo.png"
    assert resolve_image_path(url, Path(".")) == url


def test_postprocess_html_images(tmp_path: Path):
    img_file = tmp_path / "logo.svg"
    img_file.write_text("<svg></svg>", encoding="utf-8")

    raw_html = '<p><img src="logo.svg" alt="logo" width="100"></p>'
    processed = postprocess_html_images(raw_html, tmp_path, watch_mode=False)

    assert "data:image/svg+xml;base64," in processed
    assert 'width="100"' in processed
