"""Custom renderer rules and image resolution for mview."""

from __future__ import annotations

import base64
import html
import mimetypes
from pathlib import Path
import re
from typing import Any, Mapping
import urllib.parse

from markdown_it import MarkdownIt
from markdown_it.token import Token


def resolve_image_path(src: str, base_dir: Path, watch_mode: bool = False) -> str:
    """Resolve an image src attribute against the markdown file's directory.

    In static mode: embeds local images as Base64 data URIs so the generated HTML
    is fully self-contained and avoids browser file:// cross-origin blocks.
    In watch mode: routes local images through the watcher HTTP server (/_file?path=...).
    """
    if not src or src.startswith(("http://", "https://", "//", "data:", "blob:")):
        return src

    # Handle file:// URI
    if src.startswith("file://"):
        parsed = urllib.parse.urlparse(src)
        clean_path = urllib.parse.unquote(parsed.path)
        # On Windows file:///D:/path strip leading slash
        if re.match(r"^/[a-zA-Z]:", clean_path):
            clean_path = clean_path[1:]
        target_path = Path(clean_path).resolve()
    else:
        # Strip query and anchor if any
        path_part = src.split("?")[0].split("#")[0]
        unquoted = urllib.parse.unquote(path_part)
        target_path = (base_dir / unquoted).resolve()

    if not target_path.is_file():
        return src

    if watch_mode:
        encoded_path = urllib.parse.quote(str(target_path).replace("\\", "/"))
        return f"/_file?path={encoded_path}"

    # Static mode: embed as data URI
    mime_type, _ = mimetypes.guess_type(str(target_path))
    if not mime_type:
        ext = target_path.suffix.lower()
        if ext == ".svg":
            mime_type = "image/svg+xml"
        elif ext in (".jpg", ".jpeg"):
            mime_type = "image/jpeg"
        elif ext == ".png":
            mime_type = "image/png"
        elif ext == ".gif":
            mime_type = "image/gif"
        elif ext == ".webp":
            mime_type = "image/webp"
        elif ext == ".ico":
            mime_type = "image/x-icon"
        elif ext == ".avif":
            mime_type = "image/avif"
        else:
            mime_type = "application/octet-stream"

    try:
        data = target_path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type};base64,{b64}"
    except Exception:
        return src


def postprocess_html_images(html_content: str, base_dir: Path, watch_mode: bool = False) -> str:
    """Find any raw <img> tags in the HTML and resolve their relative src attributes."""

    def replace_img_src(match: re.Match[str]) -> str:
        full_tag = match.group(0)
        src_attr = match.group(1)
        resolved = resolve_image_path(src_attr, base_dir, watch_mode=watch_mode)
        # Replace only the src attribute within the tag
        return full_tag.replace(f'src="{src_attr}"', f'src="{resolved}"').replace(
            f"src='{src_attr}'", f"src='{resolved}'"
        )

    return re.sub(r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>', replace_img_src, html_content)


def setup_renderer(md: MarkdownIt, base_dir: Path, watch_mode: bool = False) -> None:
    """Attach custom rendering rules to MarkdownIt."""

    original_image_rule = md.renderer.rules.get("image", md.renderer.image)

    def custom_fence(
        tokens: list[Token],
        idx: int,
        options: Mapping[str, Any],
        env: dict[str, Any],
    ) -> str:
        token = tokens[idx]
        info = (token.info or "").strip()
        lang = info.split()[0] if info else ""
        escaped_code = html.escape(token.content)

        if lang.lower() == "mermaid":
            # Render as pre.mermaid for mermaid.js to process on page load
            return f'<pre class="mermaid">{escaped_code}</pre>\n'

        if lang:
            return (
                f'<div class="highlight highlight-source-{html.escape(lang.lower())}">'
                f'<pre><code class="language-{html.escape(lang)}">{escaped_code}</code></pre>'
                f'</div>\n'
            )

        return f'<div class="highlight"><pre><code>{escaped_code}</code></pre></div>\n'

    def custom_image(
        tokens: list[Token],
        idx: int,
        options: Mapping[str, Any],
        env: dict[str, Any],
    ) -> str:
        token = tokens[idx]
        src = token.attrGet("src")
        if src:
            token.attrSet("src", resolve_image_path(src, base_dir, watch_mode=watch_mode))
        # Delegate to original image renderer
        return original_image_rule(tokens, idx, options, env)

    md.renderer.rules["fence"] = custom_fence
    md.renderer.rules["image"] = custom_image
