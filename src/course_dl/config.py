"""Credential and unit code resolution."""

from __future__ import annotations

import getpass
import os
import re
from pathlib import Path


def resolve_credentials(
    cli_username: str | None = None,
    cli_password: str | None = None,
) -> tuple[str, str]:
    """Resolve credentials from CLI args -> env vars -> interactive prompt."""
    username = cli_username or os.environ.get("CDL_USERNAME")
    password = cli_password or os.environ.get("CDL_PASSWORD")

    if not username:
        username = input("Curtin username: ").strip()
    if not password:
        password = getpass.getpass("Curtin password: ")

    if not username or not password:
        raise SystemExit("Error: username and password are required.")

    return username, password


_UNIT_CODE_RE = re.compile(r"^[A-Z]{4}\d{4}$")


def validate_unit_code(code: str) -> str:
    """Validate and normalize a unit code."""
    code = code.strip().upper()
    if not _UNIT_CODE_RE.match(code):
        raise ValueError(f"Invalid unit code: {code!r} (expected format: COMP1000)")
    return code


def resolve_unit_codes(
    cli_units: list[str] | None = None,
    file_path: Path | None = None,
) -> list[str]:
    """Resolve unit codes from CLI args -> file -> interactive prompt."""
    raw_codes: list[str] = []

    if cli_units:
        raw_codes = cli_units
    elif file_path:
        if not file_path.exists():
            raise SystemExit(f"Error: file not found: {file_path}")
        text = file_path.read_text()
        raw_codes = re.split(r"[,\n]+", text)
    else:
        user_input = input("Enter unit codes (comma-separated): ").strip()
        if not user_input:
            raise SystemExit("Error: no unit codes provided.")
        raw_codes = user_input.split(",")

    codes = []
    for raw in raw_codes:
        raw = raw.strip()
        if not raw:
            continue
        codes.append(validate_unit_code(raw))

    if not codes:
        raise SystemExit("Error: no valid unit codes provided.")

    return codes
