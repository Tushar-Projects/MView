"""Tests for markdown parsing and GitHub-Flavored Markdown extensions."""

import pytest
from mview.parser import create_markdown_parser, github_slugify


def test_github_slugify():
    seen = set()
    assert github_slugify("Hello World", seen) == "hello-world"
    assert github_slugify("Hello World", seen) == "hello-world-1"
    assert github_slugify("Hello World", seen) == "hello-world-2"
    assert github_slugify("Special !@# Characters $ % ^ & * ()", seen) == "special-characters"
    assert github_slugify("  Padded   Spaces  ", seen) == "padded-spaces"
    assert github_slugify("", seen) == "section"


def test_heading_anchors():
    parser = create_markdown_parser()
    html = parser.render("# First Title\n\n## Sub Title\n\n# First Title")

    assert 'id="first-title"' in html
    assert 'href="#first-title"' in html
    assert 'id="sub-title"' in html
    assert 'href="#sub-title"' in html
    assert 'id="first-title-1"' in html
    assert 'href="#first-title-1"' in html
    assert 'class="anchor"' in html
    assert 'class="octicon octicon-link"' in html


def test_task_lists():
    parser = create_markdown_parser()
    html = parser.render("- [ ] Incomplete\n- [x] Complete")

    assert 'class="contains-task-list"' in html
    assert 'class="task-list-item"' in html
    assert 'class="task-list-item-checkbox"' in html
    assert 'checked="checked"' in html


def test_tables():
    parser = create_markdown_parser()
    md = "| Col 1 | Col 2 |\n| :--- | :---: |\n| Val 1 | Val 2 |"
    html = parser.render(md)

    assert "<table>" in html
    assert "<thead>" in html
    assert "<tbody>" in html
    assert "Val 1" in html


def test_strikethrough_and_autolinks():
    parser = create_markdown_parser()
    html = parser.render("~~deleted text~~ and https://github.com")

    assert "<s>deleted text</s>" in html or "<del>deleted text</del>" in html
    assert '<a href="https://github.com">https://github.com</a>' in html


def test_footnotes():
    parser = create_markdown_parser()
    html = parser.render("Text with note[^1].\n\n[^1]: Note details.")

    assert 'class="footnote-ref"' in html
    assert 'class="footnotes"' in html
    assert 'class="footnote-item"' in html
    assert "Note details." in html


def test_emoji_shortcodes():
    parser = create_markdown_parser()
    html = parser.render("Launch :rocket: and celebrate :tada:")

    assert "🚀" in html
    assert "🎉" in html


def test_github_alerts():
    parser = create_markdown_parser()
    html = parser.render("> [!NOTE]\n> Helpful note text.")

    assert 'class="markdown-alert markdown-alert-note"' in html
    assert 'class="markdown-alert-title"' in html
    assert "Helpful note text." in html
