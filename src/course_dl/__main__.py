"""Entry point for course-dl."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from course_dl.auth import login
from course_dl.cli import build_parser
from course_dl.config import resolve_credentials, resolve_unit_codes
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

    # When --all is used, unit codes are optional
    unit_codes: list[str] | None = None
    if not args.download_all:
        if args.units or args.file:
            unit_codes = resolve_unit_codes(args.units or None, args.file)
        else:
            unit_codes = resolve_unit_codes(None, None)

    if unit_codes:
        print(f"Will export courses for: {', '.join(unit_codes)}")
    else:
        print("Will export all available courses")
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
            unit_codes,
            args.output_dir,
            download_all=args.download_all,
            overwrite=args.overwrite,
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
