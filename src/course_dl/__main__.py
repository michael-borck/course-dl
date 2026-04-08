"""Entry point for course-dl."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from course_dl.auth import login
from course_dl.cli import build_parser
from course_dl.config import resolve_credentials, resolve_search_terms
from course_dl.exporter import (
    build_packages,
    download_packages,
    get_available_courses,
    select_targets,
)


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


def _print_summary(results: dict[str, str]) -> None:
    ok = [c for c, s in results.items() if s in ("ok", "queued")]
    skipped = [c for c, s in results.items() if s == "skipped"]
    not_ready = [c for c, s in results.items() if s == "not ready"]
    failed = [(c, s) for c, s in results.items()
              if s not in ("ok", "queued", "skipped", "not ready")]

    print("\n=== Summary ===")
    if ok:
        print(f"  Success: {', '.join(c[:40] for c in ok)}")
    if skipped:
        print(f"  Skipped: {', '.join(c[:40] for c in skipped)}")
    if not_ready:
        print(f"  Not ready yet: {', '.join(c[:40] for c in not_ready)}")
    if failed:
        print("  Failed:")
        for name, err in failed:
            print(f"    {name[:40]}: {err}")

    if failed:
        raise SystemExit(1)


def main() -> None:
    _load_env()
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        raise SystemExit(0)

    username, password = resolve_credentials(args.username, args.password)
    search_terms: list[str] | None = None
    if not args.select_all:
        search_terms = resolve_search_terms(args.search or None, args.file)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.visible)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        login(page, username, password, timeout=args.timeout)

        available = get_available_courses(page, timeout=args.timeout)
        if not available:
            print("No courses found in Blackboard.")
            browser.close()
            raise SystemExit(1)

        targets = select_targets(
            available, search_terms,
            select_all=args.select_all,
            match_threshold=args.match_threshold,
        )
        if not targets:
            print("No courses selected.")
            browser.close()
            raise SystemExit(0)

        print(f"\nSelected {len(targets)} course(s):")
        for c in targets:
            print(f"  - {c['name']}")

        if args.command == "build":
            results = build_packages(page, targets, timeout=args.timeout)
            _print_summary(results)
            print("\nPackages are building on Blackboard (15-30 mins).")
            print("Run 'course-dl download' with the same search terms when ready.")

        elif args.command == "download":
            results = download_packages(
                page, targets, args.output_dir,
                overwrite=args.overwrite, timeout=args.timeout,
            )
            _print_summary(results)

        browser.close()


if __name__ == "__main__":
    main()
