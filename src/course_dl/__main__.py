"""Entry point for course-dl."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from course_dl.auth import login
from course_dl.cli import build_parser
from course_dl.config import resolve_credentials, resolve_search_terms
from course_dl.exporter import export_courses


def _load_env() -> None:
    """Load .env from ~/.config/course-dl/, then ~/.course-dl.env, then CWD."""
    candidates = [
        Path.home() / ".config" / "course-dl" / ".env",
        Path.home() / ".course-dl.env",
        Path.cwd() / ".env",
    ]
    for path in candidates:
        if path.is_file():
            load_dotenv(path)
            return
    load_dotenv()


def main() -> None:
    _load_env()
    parser = build_parser()
    args = parser.parse_args()

    username, password = resolve_credentials(args.username, args.password)

    # Resolve search terms (None = interactive picker later)
    search_terms: list[str] | None = None
    if not args.download_all:
        search_terms = resolve_search_terms(args.search or None, args.file)

    if args.download_all:
        print("Will export all available courses")
    elif search_terms:
        print(f"Will search for: {', '.join(search_terms)}")
    else:
        print("No search terms — will show interactive picker after login")

    print(f"Output directory: {args.output_dir}")
    if not args.overwrite:
        print("Skipping already-downloaded courses (use --overwrite to re-download)")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.visible)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        login(page, username, password, timeout=args.timeout)
        results = export_courses(
            page,
            search_terms,
            args.output_dir,
            download_all=args.download_all,
            overwrite=args.overwrite,
            match_threshold=args.match_threshold,
            timeout=args.timeout,
        )

        browser.close()

    # Summary
    print("\n=== Summary ===")
    ok = [c for c, s in results.items() if s == "ok"]
    skipped = [c for c, s in results.items() if s == "skipped"]
    failed = [(c, s) for c, s in results.items() if s not in ("ok", "skipped")]

    if ok:
        print(f"  Exported: {', '.join(ok)}")
    if skipped:
        print(f"  Skipped (already exists): {', '.join(skipped)}")
    if failed:
        print("  Failed:")
        for code, err in failed:
            print(f"    {code}: {err}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
