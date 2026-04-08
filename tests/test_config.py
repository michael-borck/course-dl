"""Tests for config module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from course_dl.config import resolve_unit_codes, validate_unit_code


class TestValidateUnitCode:
    def test_valid_code(self) -> None:
        assert validate_unit_code("COMP1000") == "COMP1000"

    def test_lowercase_normalized(self) -> None:
        assert validate_unit_code("comp1000") == "COMP1000"

    def test_whitespace_stripped(self) -> None:
        assert validate_unit_code("  ISAD1000  ") == "ISAD1000"

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid unit code"):
            validate_unit_code("ABC123")

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="Invalid unit code"):
            validate_unit_code("")


class TestResolveUnitCodes:
    def test_cli_args(self) -> None:
        codes = resolve_unit_codes(["COMP1000", "ISAD1000"], None)
        assert codes == ["COMP1000", "ISAD1000"]

    def test_file_newline_separated(self, tmp_path: Path) -> None:
        f = tmp_path / "units.txt"
        f.write_text("COMP1000\nISAD1000\n")
        codes = resolve_unit_codes(None, f)
        assert codes == ["COMP1000", "ISAD1000"]

    def test_file_comma_separated(self, tmp_path: Path) -> None:
        f = tmp_path / "units.txt"
        f.write_text("COMP1000,ISAD1000")
        codes = resolve_unit_codes(None, f)
        assert codes == ["COMP1000", "ISAD1000"]

    def test_file_not_found(self) -> None:
        with pytest.raises(SystemExit, match="file not found"):
            resolve_unit_codes(None, Path("/nonexistent"))

    def test_interactive_prompt(self) -> None:
        with patch("builtins.input", return_value="COMP1000, ISAD1000"):
            codes = resolve_unit_codes(None, None)
        assert codes == ["COMP1000", "ISAD1000"]
