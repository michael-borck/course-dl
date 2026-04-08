"""CLI argument parsing with subcommands."""

import argparse
from pathlib import Path


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments shared by build and download subcommands."""
    parser.add_argument(
        "search",
        nargs="*",
        help=(
            "Search terms to match courses (e.g. COMP1000 'Data Structures'). "
            "Fuzzy-matched against course titles. "
            "If omitted, an interactive picker is shown."
        ),
    )
    parser.add_argument(
        "-f", "--file", type=Path,
        help="File containing search terms (one per line)",
    )
    parser.add_argument(
        "--all", action="store_true", dest="select_all",
        help="Select all courses visible in Blackboard",
    )
    parser.add_argument(
        "--match-threshold", type=int, default=60,
        help="Fuzzy match score threshold 0-100 (default: 60)",
    )


_VERSION = "0.3.1"
_REPO_URL = "https://github.com/michael-borck/course-dl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="course-dl",
        description="Download Blackboard course exports from Curtin LMS",
    )
    parser.add_argument(
        "-V", "--version", action="version",
        version=f"%(prog)s {_VERSION}\n{_REPO_URL}",
    )
    parser.add_argument("-u", "--username", help="Curtin username")
    parser.add_argument("-p", "--password", help="Curtin password")
    parser.add_argument(
        "--visible", action="store_true",
        help="Show the browser window (default: headless)",
    )
    parser.add_argument(
        "--timeout", type=int, default=60000,
        help="Navigation timeout in milliseconds (default: 60000)",
    )

    sub = parser.add_subparsers(dest="command")

    # --- build ---
    build = sub.add_parser(
        "build",
        help="Trigger Common Cartridge package builds on Blackboard",
    )
    _add_common_args(build)

    # --- download ---
    dl = sub.add_parser(
        "download",
        help="Download ready packages from Blackboard",
    )
    _add_common_args(dl)
    dl.add_argument(
        "-o", "--output-dir", type=Path, default=Path("exports"),
        help="Output directory for downloads (default: ./exports/)",
    )
    dl.add_argument(
        "--overwrite", action="store_true",
        help="Re-download courses that already exist locally",
    )

    return parser
