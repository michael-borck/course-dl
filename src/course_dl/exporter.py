"""Blackboard course export: build and download logic."""

from __future__ import annotations

import re
from pathlib import Path

from InquirerPy import inquirer
from playwright.sync_api import Frame, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from rapidfuzz import fuzz

BLACKBOARD_COURSES_URL = "https://lms.curtin.edu.au/ultra/course"
BASE_URL = "https://lms.curtin.edu.au"


# ---------------------------------------------------------------------------
# Course list & selection
# ---------------------------------------------------------------------------

def get_available_courses(page: Page, timeout: int = 60000) -> list[dict[str, str]]:
    """Get list of courses from Blackboard Ultra courses page."""
    print("Fetching course list...")
    page.goto(BLACKBOARD_COURSES_URL, wait_until="networkidle", timeout=timeout)
    page.wait_for_timeout(3000)

    course_links = page.query_selector_all("a.course-title")
    courses: list[dict[str, str]] = []
    for i, link in enumerate(course_links):
        name = (link.inner_text() or "").strip()
        if name:
            courses.append({"name": name, "index": str(i)})

    print(f"  Found {len(courses)} courses")
    return courses


def select_targets(
    available: list[dict[str, str]],
    search_terms: list[str] | None,
    select_all: bool = False,
    match_threshold: int = 60,
) -> list[dict[str, str]]:
    """Select target courses via --all, search terms, or interactive picker."""
    print("\nAvailable courses:")
    for i, c in enumerate(available, 1):
        print(f"  {i}. {c['name']}")

    if select_all:
        return available

    if search_terms:
        print(f"\nMatching search terms (threshold: {match_threshold})...")
        return fuzzy_match_courses(available, search_terms, match_threshold)

    print()
    return interactive_pick(available)


def fuzzy_match_courses(
    available: list[dict[str, str]],
    search_terms: list[str],
    threshold: int = 60,
) -> list[dict[str, str]]:
    """Match courses using fuzzy string matching against search terms."""
    matched: list[dict[str, str]] = []
    seen: set[str] = set()

    for term in search_terms:
        best_score = 0
        best_course: dict[str, str] | None = None

        for course in available:
            name = course["name"]
            score = max(
                fuzz.token_set_ratio(term.lower(), name.lower()),
                fuzz.partial_ratio(term.lower(), name.lower()),
            )
            if score > best_score:
                best_score = score
                best_course = course

        if best_course and best_score >= threshold and best_course["name"] not in seen:
            print(f"  '{term}' -> {best_course['name'][:80]} (score: {best_score})")
            matched.append(best_course)
            seen.add(best_course["name"])
        else:
            print(f"  '{term}' -> no match (best score: {best_score}, threshold: {threshold})")

    return matched


def interactive_pick(available: list[dict[str, str]]) -> list[dict[str, str]]:
    """Show an interactive checkbox picker for course selection."""
    if not available:
        return []

    choices = [{"name": c["name"], "value": i} for i, c in enumerate(available)]
    selected = inquirer.checkbox(
        message="Select courses to export (space to toggle, enter to confirm):",
        choices=choices,
    ).execute()

    return [available[i] for i in selected]


# ---------------------------------------------------------------------------
# Skip detection
# ---------------------------------------------------------------------------

def already_downloaded(course_name: str, output_dir: Path) -> bool:
    """Check if an export already exists locally for this course."""
    if not output_dir.exists():
        return False

    code_match = re.search(r"[A-Z]{4}\d{4}", course_name.upper())
    if not code_match:
        return False

    code = code_match.group(0)
    for f in output_dir.iterdir():
        if code in f.name.upper() and f.suffix in (".zip", ".imscc"):
            return True
    return False


# ---------------------------------------------------------------------------
# Step 1: Build (trigger CC exports)
# ---------------------------------------------------------------------------

def build_packages(
    page: Page,
    targets: list[dict[str, str]],
    timeout: int = 60000,
) -> dict[str, str]:
    """Trigger Common Cartridge builds for target courses.

    Returns {course_name: status}.
    """
    results: dict[str, str] = {}

    for course in targets:
        label = course["name"]
        print(f"\n--- {label[:80]} ---")

        try:
            _navigate_to_course(page, course, timeout)
            _trigger_cc_build(page, timeout)
            results[label] = "queued"
            print("  Build queued successfully")
        except Exception as e:
            print(f"  Error: {e}")
            results[label] = str(e)

    return results


# ---------------------------------------------------------------------------
# Step 2: Download
# ---------------------------------------------------------------------------

def download_packages(
    page: Page,
    targets: list[dict[str, str]],
    output_dir: Path,
    overwrite: bool = False,
    timeout: int = 60000,
) -> dict[str, str]:
    """Download ready packages for target courses.

    Returns {course_name: status}.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}

    for course in targets:
        name = course["name"]
        print(f"\n--- {name[:80]} ---")

        if not overwrite and already_downloaded(name, output_dir):
            print("  Already downloaded locally, skipping (use --overwrite)")
            results[name] = "skipped"
            continue

        try:
            packages = _get_packages(page, course, timeout)

            if not packages:
                print("  No packages ready yet — try again later")
                results[name] = "not ready"
                continue

            pkg = packages[0]
            print(f"  Found: {pkg['name']}")

            if len(packages) > 1:
                print(f"  ({len(packages)} packages available, downloading most recent)")
                for p in packages[1:]:
                    print(f"    also available: {p['name']}")

            _download_file(page, pkg, output_dir, timeout)
            results[name] = "ok"

            # Clean up: delete from BB only if it was the sole package
            if len(packages) == 1:
                _delete_package(page, pkg, timeout)
                print("  Cleaned up package from Blackboard")
            else:
                print("  Multiple packages exist — skipping Blackboard cleanup")

        except Exception as e:
            print(f"  Error: {e}")
            results[name] = str(e)

    return results


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

def _navigate_to_course(page: Page, course: dict[str, str], timeout: int) -> None:
    """Navigate to a course by clicking its link on the courses page."""
    print("  Navigating to course...")
    page.goto(BLACKBOARD_COURSES_URL, wait_until="networkidle", timeout=timeout)
    page.wait_for_timeout(3000)

    course_links = page.query_selector_all("a.course-title")
    idx = int(course["index"])
    if idx >= len(course_links):
        raise RuntimeError("Course link no longer at expected position")

    course_links[idx].click()
    page.wait_for_timeout(5000)
    page.wait_for_load_state("networkidle", timeout=timeout)


def _get_classic_frame(page: Page) -> Frame | None:
    """Find the classic Blackboard iframe within Ultra."""
    for frame in page.frames:
        if "webapps" in frame.url and "execute" in frame.url:
            return frame
    return None


def _get_frame_by_url(page: Page, url_fragment: str) -> Frame | None:
    """Find a frame whose URL contains the given fragment."""
    for frame in page.frames:
        if url_fragment in frame.url:
            return frame
    return None


def _navigate_to_archive(page: Page, timeout: int) -> Frame:
    """Navigate sidebar to Export/Archive page, return the frame."""
    classic_frame = _get_classic_frame(page)
    if not classic_frame:
        raise RuntimeError("Classic Blackboard frame not found")

    pkg_link = classic_frame.query_selector("a:has-text('Packages and Utilities')")
    if not pkg_link:
        raise RuntimeError("'Packages and Utilities' not found in sidebar")
    pkg_link.click()
    page.wait_for_timeout(1000)

    export_link = classic_frame.query_selector("a:has-text('Export/Archive Course')")
    if not export_link:
        raise RuntimeError("'Export/Archive Course' link not found")
    export_link.click()
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle", timeout=timeout)

    archive_frame = _get_frame_by_url(page, "archive_manager")
    if not archive_frame:
        raise RuntimeError("Archive manager frame not found")

    return archive_frame


def _read_packages_table(archive_frame: Frame) -> list[dict[str, str]]:
    """Read available packages from the archive manager table."""
    packages: list[dict[str, str]] = []
    rows = archive_frame.query_selector_all("#userCreatedPackagesList_datatable tr")
    for row in rows[1:]:
        # Search all cells — column order may vary due to sorting
        for link in row.query_selector_all("a"):
            href = link.get_attribute("href") or ""
            if "/bbcswebdav/" in href:
                name = (link.inner_text() or "").strip()
                if name:
                    packages.append({"name": name, "href": href})
                break
    return packages


# ---------------------------------------------------------------------------
# Build step internals
# ---------------------------------------------------------------------------

def _trigger_cc_build(page: Page, timeout: int) -> None:
    """Navigate sidebar to Export/Archive, trigger CC export."""
    archive_frame = _navigate_to_archive(page, timeout)

    cc_link = archive_frame.query_selector(
        "a:has-text('Export Common Cartridge Package')"
    )
    if not cc_link:
        raise RuntimeError("'Export Common Cartridge Package' link not found")

    print("  Clicking Export Common Cartridge Package...")
    cc_link.click()
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle", timeout=timeout)

    cc_frame = _get_frame_by_url(page, "commonCartridge")
    if not cc_frame:
        cc_frame = _get_frame_by_url(page, "contentExchange")
    if not cc_frame:
        raise RuntimeError("Common Cartridge export form not found")

    submit_btn = cc_frame.query_selector("input[name='bottom_Submit']")
    if not submit_btn:
        raise RuntimeError("Submit button not found on CC export form")

    print("  Submitting build request...")
    submit_btn.click()
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle", timeout=timeout)

    # Verify success message
    archive_frame = _get_frame_by_url(page, "archive_manager")
    if archive_frame:
        receipt = archive_frame.query_selector(".receipt, #goodMsg1")
        if receipt:
            msg = (receipt.inner_text() or "").strip()[:100]
            print(f"  Blackboard says: {msg}")


# ---------------------------------------------------------------------------
# Download step internals
# ---------------------------------------------------------------------------

def _get_packages(
    page: Page, course: dict[str, str], timeout: int
) -> list[dict[str, str]]:
    """Navigate to Export/Archive page and list available packages."""
    _navigate_to_course(page, course, timeout)
    archive_frame = _navigate_to_archive(page, timeout)
    return _read_packages_table(archive_frame)


def _download_file(
    page: Page,
    package: dict[str, str],
    output_dir: Path,
    timeout: int,
) -> None:
    """Download a package file by clicking its link."""
    archive_frame = _get_frame_by_url(page, "archive_manager")
    if not archive_frame:
        raise RuntimeError("Archive frame not found for download")

    link = archive_frame.query_selector(f"a[href='{package['href']}']")
    if not link:
        raise RuntimeError("Download link not found in table")

    print("  Downloading...")
    with page.expect_download(timeout=timeout) as download_info:
        link.click()
    download = download_info.value

    filename = download.suggested_filename or f"{package['name']}.zip"
    dest = output_dir / filename
    download.save_as(dest)
    print(f"  Saved: {dest}")


def _delete_package(
    page: Page,
    package: dict[str, str],
    timeout: int,
) -> None:
    """Delete a package from Blackboard (only when it's the sole package)."""
    archive_frame = _get_frame_by_url(page, "archive_manager")
    if not archive_frame:
        return

    checkboxes = archive_frame.query_selector_all(
        "#userCreatedPackagesList_datatable input[type='checkbox']"
    )
    if len(checkboxes) == 1:
        checkboxes[0].check()
        page.wait_for_timeout(500)

        delete_btn = archive_frame.query_selector(
            "input[value='Delete'], button:has-text('Delete'), a:has-text('Delete')"
        )
        if delete_btn:
            delete_btn.click()
            page.wait_for_timeout(2000)
            ok_btn = archive_frame.query_selector(
                "input[value='OK'], button:has-text('OK')"
            )
            if ok_btn:
                ok_btn.click()
                page.wait_for_timeout(2000)
