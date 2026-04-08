"""Tests for config module."""

from __future__ import annotations

from pathlib import Path

import pytest

from course_dl.config import resolve_search_terms


class TestResolveSearchTerms:
    def test_cli_args(self) -> None:
        terms = resolve_search_terms(["COMP1000", "Data Structures"], None)
        assert terms == ["COMP1000", "Data Structures"]

    def test_preserves_case_and_spaces(self) -> None:
        terms = resolve_search_terms(["Introduction to Programming"], None)
        assert terms == ["Introduction to Programming"]

    def test_file_newline_separated(self, tmp_path: Path) -> None:
        f = tmp_path / "terms.txt"
        f.write_text("COMP1000\nData Structures\n")
        terms = resolve_search_terms(None, f)
        assert terms == ["COMP1000", "Data Structures"]

    def test_file_preserves_commas(self, tmp_path: Path) -> None:
        f = tmp_path / "terms.txt"
        f.write_text("Unix, C and Systems Programming\nCOMP1000\n")
        terms = resolve_search_terms(None, f)
        assert terms == ["Unix, C and Systems Programming", "COMP1000"]

    def test_file_not_found(self) -> None:
        with pytest.raises(SystemExit, match="file not found"):
            resolve_search_terms(None, Path("/nonexistent"))

    def test_no_input_returns_none(self) -> None:
        result = resolve_search_terms(None, None)
        assert result is None

    def test_empty_list_returns_none(self) -> None:
        result = resolve_search_terms([], None)
        assert result is None

    def test_whitespace_only_returns_none(self) -> None:
        result = resolve_search_terms(["  ", ""], None)
        assert result is None
