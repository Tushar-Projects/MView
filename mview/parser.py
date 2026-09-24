"""Markdown parser configuration and AST processing for mview."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable, Set

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

try:
    import emoji
except ImportError:
    emoji = None

if TYPE_CHECKING:
    from markdown_it.rules_core import StateCore

# Octicon SVGs for GitHub-style elements
OCTICON_LINK_SVG = (
    '<svg class="octicon octicon-link" viewBox="0 0 16 16" version="1.1" '
    'width="16" height="16" aria-hidden="true">'
    '<path d="m7.775 3.275 1.25-1.25a3.5 3.5 0 1 1 4.95 4.95l-2.5 2.5a3.5 3.5 0 0 1-4.95 0 '
    '.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018 1.998 1.998 0 0 0 2.83 0l2.5-2.5a2.002 '
    '2.002 0 0 0-2.83-2.83l-1.25 1.25a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042Zm-4.69 '
    '9.64a1.998 1.998 0 0 0 2.83 0l1.25-1.25a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 '
    '1.042l-1.25 1.25a3.5 3.5 0 1 1-4.95-4.95l2.5-2.5a3.5 3.5 0 0 1 4.95 0 .751.751 0 0 1-.018 '
    '1.042l-1.042.018 1.998 1.998 0 0 0-2.83 0l-2.5 2.5a1.998 1.998 0 0 0 0 2.83Z"></path>'
    '</svg>'
)

ALERT_ICONS = {
    "note": (
        '<svg class="octicon octicon-info" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true">'
        '<path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-6.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM6.5 7.75A.75.75 0 0 1 7.25 7h1a.75.75 0 0 1 .75.75v2.75h.25a.75.75 0 0 1 0 1.5h-2a.75.75 0 0 1 0-1.5h.25v-2h-.25a.75.75 0 0 1-.75-.75ZM8 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"></path>'
        '</svg>'
    ),
    "tip": (
        '<svg class="octicon octicon-light-bulb" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true">'
        '<path d="M8 1.5c-2.363 0-4 1.69-4 3.75 0 .761.233 1.574.814 2.222.428.477.842 1.08.842 1.828v.2a1 1 0 0 0 1 1h2.688a1 1 0 0 0 1-1v-.2c0-.748.414-1.35.842-1.828.581-.648.814-1.461.814-2.222 0-2.06-1.637-3.75-4-3.75ZM6 12a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1v-.5H6V12Zm-1.688-6.75c0-1.28 1.055-2.25 2.688-2.25s2.688.97 2.688 2.25c0 .416-.145.92-.516 1.334-.582.65-1.172 1.458-1.172 2.416H7c0-.958-.59-1.766-1.172-2.416-.371-.414-.516-.918-.516-1.334Z"></path>'
        '</svg>'
    ),
    "important": (
        '<svg class="octicon octicon-report" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true">'
        '<path d="M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v9.5A1.75 1.75 0 0 1 14.25 13H9.06l-2.573 2.573A1.458 1.458 0 0 1 4 14.543V13H1.75A1.75 1.75 0 0 1 0 11.25Zm1.75-.25a.25.25 0 0 0-.25.25v9.5c0 .138.112.25.25.25h3a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.749.749 0 0 1 .53-.22h5.5a.25.25 0 0 0 .25-.25v-9.5a.25.25 0 0 0-.25-.25Zm6.25 2a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5a.75.75 0 0 1 .75-.75Zm0 7a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"></path>'
        '</svg>'
    ),
    "warning": (
        '<svg class="octicon octicon-alert" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true">'
        '<path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"></path>'
        '</svg>'
    ),
    "caution": (
        '<svg class="octicon octicon-stop" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true">'
        '<path d="M4.47.047A1.75 1.75 0 0 1 5.71 0h4.58c.464 0 .91.184 1.238.513l4.96 4.96c.328.328.512.774.512 1.238v4.58c0 .464-.184.91-.513 1.238l-4.96 4.96c-.328.328-.774.512-1.238.512H5.71a1.75 1.75 0 0 1-1.238-.513L.488 11.53A1.75 1.75 0 0 1 0 10.292V5.712c0-.464.184-.91.513-1.238ZM5.71 1.5a.25.25 0 0 0-.177.073L.573 6.533a.25.25 0 0 0-.073.177v4.582c0 .066.026.13.073.177l4.96 4.96c.047.047.111.073.177.073h4.58a.25.25 0 0 0 .177-.073l4.96-4.96a.25.25 0 0 0 .073-.177V6.71a.25.25 0 0 0-.073-.177l-4.96-4.96A.25.25 0 0 0 10.29 1.5ZM8 4a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 8 4Zm0 7a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"></path>'
        '</svg>'
    ),
}


def github_slugify(text: str, seen_slugs: Set[str]) -> str:
    """Generate a GitHub-compliant slug from heading text, ensuring uniqueness."""
    cleaned = re.sub(r"<[^>]+>", "", text).strip().lower()
    slug = re.sub(r"[^\w\s-]", "", cleaned)
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    if not slug:
        slug = "section"

    candidate = slug
    counter = 1
    while candidate in seen_slugs:
        candidate = f"{slug}-{counter}"
        counter += 1

    seen_slugs.add(candidate)
    return candidate


def github_heading_anchors_plugin(md: MarkdownIt) -> None:
    """Add GitHub-style slugged anchor IDs and hover anchor links to all headings."""

    def _heading_anchor_rule(state: StateCore) -> None:
        seen_slugs: Set[str] = set()

        for idx, token in enumerate(state.tokens):
            if token.type != "heading_open":
                continue

            inline_token = state.tokens[idx + 1]
            if inline_token.children is None:
                continue

            title_text = "".join(
                child.content
                for child in inline_token.children
                if child.type in ("text", "code_inline")
            )

            slug = github_slugify(title_text, seen_slugs)
            token.attrSet("id", slug)

            link_open = Token("link_open", "a", 1)
            link_open.attrSet("class", "anchor")
            link_open.attrSet("aria-hidden", "true")
            link_open.attrSet("href", f"#{slug}")

            svg_token = Token("html_inline", "", 0, content=OCTICON_LINK_SVG)
            link_close = Token("link_close", "a", -1)

            inline_token.children = [link_open, svg_token, link_close] + inline_token.children

    md.core.ruler.push("github_heading_anchors", _heading_anchor_rule)


def github_emoji_plugin(md: MarkdownIt) -> None:
    """Convert emoji shortcodes like :rocket: into actual emojis in plain text."""
    if emoji is None:
        return

    def _emoji_rule(state: StateCore) -> None:
        for token in state.tokens:
            if token.type == "inline" and token.children:
                for child in token.children:
                    if child.type == "text" and ":" in child.content:
                        child.content = emoji.emojize(child.content, language="alias")

    md.core.ruler.push("github_emoji", _emoji_rule)


def github_alerts_plugin(md: MarkdownIt) -> None:
    """Transform GitHub callouts like `> [!NOTE]` into .markdown-alert containers."""
    alert_pattern = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*", re.IGNORECASE)

    def _alerts_rule(state: StateCore) -> None:
        i = 0
        while i < len(state.tokens):
            token = state.tokens[i]
            if token.type == "blockquote_open":
                # Look for paragraph open immediately following blockquote_open
                if i + 2 < len(state.tokens) and state.tokens[i + 1].type == "paragraph_open":
                    inline_token = state.tokens[i + 2]
                    if inline_token.type == "inline" and inline_token.children:
                        first_child = inline_token.children[0]
                        if first_child.type == "text":
                            match = alert_pattern.match(first_child.content)
                            if match:
                                alert_type = match.group(1).lower()
                                title = alert_type.capitalize()
                                icon_svg = ALERT_ICONS.get(alert_type, "")

                                # Remove the [!NOTE] prefix from text
                                first_child.content = first_child.content[match.end() :]
                                if not first_child.content.strip():
                                    inline_token.children.pop(0)

                                # Change blockquote tokens to div.markdown-alert
                                token.tag = "div"
                                token.attrSet("class", f"markdown-alert markdown-alert-{alert_type}")

                                # Insert title paragraph token right after div.markdown-alert
                                title_p_open = Token("paragraph_open", "p", 1)
                                title_p_open.attrSet("class", "markdown-alert-title")

                                title_inline = Token("inline", "", 0)
                                title_inline.children = [
                                    Token("html_inline", "", 0, content=icon_svg),
                                    Token("text", "", 0, content=f" {title}"),
                                ]

                                title_p_close = Token("paragraph_close", "p", -1)

                                # Insert title tokens before the first content paragraph
                                state.tokens.insert(i + 1, title_p_close)
                                state.tokens.insert(i + 1, title_inline)
                                state.tokens.insert(i + 1, title_p_open)

                                # Find matching blockquote_close and change tag to div
                                depth = 1
                                j = i + 4
                                while j < len(state.tokens):
                                    if state.tokens[j].type == "blockquote_open":
                                        depth += 1
                                    elif state.tokens[j].type == "blockquote_close":
                                        depth -= 1
                                        if depth == 0:
                                            state.tokens[j].tag = "div"
                                            break
                                    j += 1
            i += 1

    md.core.ruler.push("github_alerts", _alerts_rule)


def create_markdown_parser() -> MarkdownIt:
    """Create and configure a MarkdownIt parser with GFM, tasklists, footnotes, anchors, emojis, and alerts."""
    md = MarkdownIt("gfm-like", {"linkify": True, "html": True, "typographer": False})

    # Enable GFM plugins
    md.use(tasklists_plugin)
    md.use(footnote_plugin)

    # Enable GitHub extensions
    md.use(github_heading_anchors_plugin)
    md.use(github_emoji_plugin)
    md.use(github_alerts_plugin)

    return md
