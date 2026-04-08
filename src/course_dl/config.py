"""Credential and search term resolution."""

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


def resolve_search_terms(
    cli_terms: list[str] | None = None,
    file_path: Path | None = None,
) -> list[str] | None:
    """Resolve search terms from CLI args -> file.

    Returns None if no terms provided (triggers interactive picker later).
    """
    raw_terms: list[str] = []

    if cli_terms:
        raw_terms = cli_terms
    elif file_path:
        if not file_path.exists():
            raise SystemExit(f"Error: file not found: {file_path}")
        text = file_path.read_text()
        raw_terms = re.split(r"[,\n]+", text)

    terms = [t.strip() for t in raw_terms if t.strip()]
    return terms if terms else None
