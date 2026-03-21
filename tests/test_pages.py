"""Tests for page utilities (wikilink parsing)."""

from app.pages import parse_wikilinks


class TestParseWikilinks:
    def test_no_links(self):
        assert parse_wikilinks("Hello world") == []

    def test_single_link(self):
        result = parse_wikilinks("Check out [[Python]]")
        assert result == ["Python"]

    def test_multiple_links(self):
        result = parse_wikilinks("See [[Python]] and [[Rust]]")
        assert set(result) == {"Python", "Rust"}

    def test_duplicate_links_deduplicated(self):
        result = parse_wikilinks("[[Python]] is great. I love [[Python]]")
        assert result == ["Python"]

    def test_link_with_spaces(self):
        result = parse_wikilinks("See [[My Notes]]")
        assert result == ["My Notes"]

    def test_link_with_date(self):
        result = parse_wikilinks("See [[2026-01-15]]")
        assert result == ["2026-01-15"]

    def test_empty_brackets_no_match(self):
        result = parse_wikilinks("See [[]]")
        assert result == []

    def test_nested_brackets(self):
        result = parse_wikilinks("See [[inner]]")
        assert result == ["inner"]

    def test_multiline_content(self):
        content = """
        First line with [[PageA]]
        Second line with [[PageB]]
        Third line with no links
        """
        result = parse_wikilinks(content)
        assert set(result) == {"PageA", "PageB"}
