"""CLI argument parsing."""

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="course-dl",
        description="Download Blackboard course exports from Curtin LMS",
    )
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
        "-f",
        "--file",
        type=Path,
        help="File containing search terms (one per line or comma-separated)",
    )
    parser.add_argument("-u", "--username", help="Curtin username")
    parser.add_argument("-p", "--password", help="Curtin password")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("exports"),
        help="Output directory for course exports (default: ./exports/)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="download_all",
        help="Download all courses visible in Blackboard (ignores search terms)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download courses that already exist locally",
    )
    parser.add_argument(
        "--match-threshold",
        type=int,
        default=60,
        help="Fuzzy match score threshold 0-100 (default: 60)",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show the browser window (default: headless)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60000,
        help="Navigation timeout in milliseconds (default: 60000)",
    )
    return parser
