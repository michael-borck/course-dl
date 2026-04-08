"""Tests for fuzzy matching logic."""

from __future__ import annotations

from course_dl.exporter import fuzzy_match_courses

COURSES = [
    {"name": "COMP1000 - Unix and C Programming - S1 2026 - Bentley Campus (AUTO_CREATED_123)", "url": "/c/1"},
    {"name": "ISAD1000 - Introduction to Application Development - S1 2026 (IMPORTED_456)", "url": "/c/2"},
    {"name": "COMP2003 - Data Structures and Algorithms - S2 2025 - Perth (AUTO_789)", "url": "/c/3"},
    {"name": "MATH1002 - Linear Algebra - S1 2026 (COPY_101)", "url": "/c/4"},
]


class TestFuzzyMatchCourses:
    def test_match_by_unit_code(self) -> None:
        result = fuzzy_match_courses(COURSES, ["COMP1000"])
        assert len(result) == 1
        assert result[0]["url"] == "/c/1"

    def test_match_by_partial_name(self) -> None:
        result = fuzzy_match_courses(COURSES, ["Data Structures"])
        assert len(result) == 1
        assert result[0]["url"] == "/c/3"

    def test_match_by_keyword(self) -> None:
        result = fuzzy_match_courses(COURSES, ["Linear Algebra"])
        assert len(result) == 1
        assert result[0]["url"] == "/c/4"

    def test_multiple_terms(self) -> None:
        result = fuzzy_match_courses(COURSES, ["COMP1000", "ISAD1000"])
        assert len(result) == 2
        urls = {c["url"] for c in result}
        assert urls == {"/c/1", "/c/2"}

    def test_no_match_below_threshold(self) -> None:
        result = fuzzy_match_courses(COURSES, ["ZZZZ9999"], threshold=80)
        assert len(result) == 0

    def test_case_insensitive(self) -> None:
        result = fuzzy_match_courses(COURSES, ["comp1000"])
        assert len(result) == 1
        assert result[0]["url"] == "/c/1"

    def test_no_duplicates(self) -> None:
        result = fuzzy_match_courses(COURSES, ["COMP1000", "Unix and C"])
        assert len(result) == 1
