"""Tests for mview CLI argument parsing and error handling."""

from pathlib import Path
import pytest

from mview.cli import parse_args, preview_static, validate_file, _find_browser_exe_win


def test_parse_args_defaults():
    args = parse_args(["document.md"])
    assert args.file == "document.md"
    assert args.watch is False
    assert args.port is None
    assert args.no_browser is False
    assert args.browser is None


def test_parse_args_watch():
    args = parse_args(["document.md", "--watch", "-p", "9000", "--no-browser"])
    assert args.file == "document.md"
    assert args.watch is True
    assert args.port == 9000
    assert args.no_browser is True


def test_parse_args_browser_options():
    args1 = parse_args(["document.md", "--browser", "firefox"])
    assert args1.browser == "firefox"

    args2 = parse_args(["document.md", "-b", "chrome"])
    assert args2.browser == "chrome"

    args3 = parse_args(["document.md", "--edge"])
    assert args3.browser == "edge"

    args4 = parse_args(["document.md", "--brave"])
    assert args4.browser == "brave"

    args5 = parse_args(["document.md", "--firefox"])
    assert args5.browser == "firefox"


def test_validate_file_missing_arg():
    with pytest.raises(SystemExit) as excinfo:
        validate_file(None)
    assert excinfo.value.code == 1


def test_validate_file_not_found():
    with pytest.raises(SystemExit) as excinfo:
        validate_file("does_not_exist_12345.md")
    assert excinfo.value.code == 1


def test_validate_file_not_md(tmp_path: Path):
    txt_file = tmp_path / "file.txt"
    txt_file.write_text("hello", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        validate_file(str(txt_file))
    assert excinfo.value.code == 1


def test_validate_file_is_dir(tmp_path: Path):
    with pytest.raises(SystemExit) as excinfo:
        validate_file(str(tmp_path))
    assert excinfo.value.code == 1


def test_validate_file_success(tmp_path: Path):
    md_file = tmp_path / "valid.md"
    md_file.write_text("# Hello", encoding="utf-8")
    validated = validate_file(str(md_file))
    assert validated == md_file.resolve()


def test_preview_static_no_browser(tmp_path: Path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Preview Test", encoding="utf-8")
    temp_html = preview_static(md_file, open_browser=False)

    assert temp_html.exists()
    assert temp_html.suffix == ".html"
    content = temp_html.read_text(encoding="utf-8")
    assert "Preview Test" in content
    assert '<main class="markdown-body">' in content

    # Clean up
    try:
        temp_html.unlink()
    except OSError:
        pass
