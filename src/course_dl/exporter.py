"""Blackboard course export download logic."""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

_UNIT_CODE_RE = re.compile(r"[A-Z]{4}\d{4}")


def get_available_courses(page: Page, timeout: int = 60000) -> list[dict[str, str]]:
    """Get list of courses available in Blackboard.

    Returns list of dicts with keys: 'name', 'url', 'unit_code'.
    """
    print("Fetching course list...")
    page.wait_for_timeout(3000)

    courses: list[dict[str, str]] = []

    # Blackboard Ultra: courses listed as links on the institution page / courses page
    # Navigate to the courses page
    courses_url = "https://lms.curtin.edu.au/ultra/course"
    page.goto(courses_url, wait_until="networkidle", timeout=timeout)
    page.wait_for_timeout(3000)

    # Look for course links — Blackboard Ultra uses course card links
    course_links = page.query_selector_all("a[href*='/ultra/courses/']")

    if not course_links:
        # Fallback: try the classic Blackboard course list
        course_links = page.query_selector_all("a[href*='/webapps/blackboard/execute/courseMain']")

    if not course_links:
        # Try broader selector for any course-like links
        course_links = page.query_selector_all(
            "[data-course-id] a, .course-element a, .course-org-list a"
        )

    for link in course_links:
        name = (link.inner_text() or "").strip()
        href = link.get_attribute("href") or ""
        if not name or not href:
            continue

        # Extract unit code from course name
        code_match = _UNIT_CODE_RE.search(name.upper())
        unit_code = code_match.group(0) if code_match else ""

        courses.append({"name": name, "url": href, "unit_code": unit_code})

    print(f"  Found {len(courses)} courses")
    return courses


def already_downloaded(unit_code: str, output_dir: Path) -> bool:
    """Check if a course export already exists for this unit code."""
    for f in output_dir.iterdir() if output_dir.exists() else []:
        if unit_code in f.name.upper() and f.suffix == ".zip":
            return True
    return False


def export_courses(
    page: Page,
    unit_codes: list[str] | None,
    output_dir: Path,
    download_all: bool = False,
    overwrite: bool = False,
    timeout: int = 60000,
) -> dict[str, str]:
    """Export and download courses from Blackboard.

    Returns a dict of {unit_code_or_name: status} where status is 'ok',
    'skipped', or an error message.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}

    available = get_available_courses(page, timeout)
    if not available:
        print("  No courses found in Blackboard.")
        return results

    # Display available courses
    print("\nAvailable courses:")
    for c in available:
        code_label = f" [{c['unit_code']}]" if c["unit_code"] else ""
        print(f"  {c['name']}{code_label}")

    # Filter to requested units
    if download_all:
        targets = available
    elif unit_codes:
        targets = []
        for code in unit_codes:
            matched = [c for c in available if c["unit_code"] == code]
            if matched:
                targets.append(matched[0])
            else:
                print(f"  Warning: {code} not found in available courses")
                results[code] = "not found in Blackboard"
    else:
        targets = available

    for course in targets:
        label = course["unit_code"] or course["name"]
        print(f"\n--- {label} ---")

        # Skip check
        if not overwrite and course["unit_code"] and already_downloaded(
            course["unit_code"], output_dir
        ):
            print("  Already downloaded, skipping (use --overwrite to re-download)")
            results[label] = "skipped"
            continue

        try:
            _export_one(page, course, output_dir, timeout)
            results[label] = "ok"
        except Exception as e:
            print(f"  Error: {e}")
            results[label] = str(e)

    return results


def _export_one(
    page: Page, course: dict[str, str], output_dir: Path, timeout: int
) -> None:
    """Export a single course from Blackboard."""
    unit_code = course["unit_code"]
    course_url = course["url"]

    # Make URL absolute if needed
    if course_url.startswith("/"):
        course_url = f"https://lms.curtin.edu.au{course_url}"

    # Navigate to the course
    print(f"  Opening course: {course['name']}")
    page.goto(course_url, wait_until="networkidle", timeout=timeout)
    page.wait_for_timeout(3000)

    # --- Navigate to course export ---
    # Blackboard Ultra: Course content area, then packages/export
    # Try Ultra flow first
    if _try_ultra_export(page, unit_code, output_dir, timeout):
        return

    # Try Classic Blackboard flow
    if _try_classic_export(page, unit_code, output_dir, timeout):
        return

    raise RuntimeError(
        f"Could not find export option for {course['name']}. "
        "Run with --visible to debug."
    )


def _try_ultra_export(
    page: Page, unit_code: str, output_dir: Path, timeout: int
) -> bool:
    """Attempt Blackboard Ultra export flow.

    Ultra path: Course page -> ... (more options) -> Export/Archive Course
    """
    # In Ultra, look for the course management / settings gear
    # Click on the course settings or three-dot menu
    settings_btn = page.query_selector(
        "[data-ng-click*='settings'], "
        "button[aria-label*='Settings'], "
        "button[aria-label*='Course settings'], "
        "a[href*='settings']"
    )
    if not settings_btn:
        # Try the three-dot menu at top-right
        settings_btn = page.query_selector(
            "button[aria-label*='More options'], "
            "button[aria-label*='Course management']"
        )

    if not settings_btn:
        return False

    settings_btn.click()
    page.wait_for_timeout(2000)

    # Look for export/archive option
    export_link = page.query_selector(
        "a:has-text('Export'), "
        "a:has-text('Archive'), "
        "button:has-text('Export'), "
        "button:has-text('Archive'), "
        "[role='menuitem']:has-text('Export')"
    )

    if not export_link:
        return False

    export_link.click()
    page.wait_for_timeout(3000)

    # Handle the export dialog — select all content
    _select_all_content(page)

    # Click submit/export button
    submit_btn = page.query_selector(
        "button:has-text('Export'), "
        "input[type='submit'][value*='Export'], "
        "button[type='submit']"
    )
    if submit_btn:
        submit_btn.click()
        page.wait_for_timeout(5000)

    # Wait for and download the export file
    return _download_export_file(page, unit_code, output_dir, timeout)


def _try_classic_export(
    page: Page, unit_code: str, output_dir: Path, timeout: int
) -> bool:
    """Attempt Classic Blackboard export flow.

    Classic path: Control Panel -> Packages and Utilities -> Export Course
    """
    # Look for Control Panel / Course Management in the sidebar
    control_panel = page.query_selector(
        "#controlPanel, "
        "a:has-text('Control Panel'), "
        "a:has-text('Course Management'), "
        "#courseMenuPalette_contents a:has-text('Packages'), "
        "a[href*='exportCourse'], "
        "a[href*='export']"
    )

    if not control_panel:
        # Try the sidebar navigation
        sidebar_links = page.query_selector_all("#courseMenuPalette_contents a, .navItem a")
        for link in sidebar_links:
            text = (link.inner_text() or "").strip().lower()
            if "package" in text or "export" in text or "control" in text:
                control_panel = link
                break

    if not control_panel:
        return False

    control_panel.click()
    page.wait_for_timeout(2000)

    # If we clicked Control Panel, navigate to Packages and Utilities -> Export
    packages_link = page.query_selector(
        "a:has-text('Packages and Utilities'), "
        "a:has-text('Packages & Utilities')"
    )
    if packages_link:
        packages_link.click()
        page.wait_for_timeout(2000)

    export_link = page.query_selector(
        "a:has-text('Export Course'), "
        "a:has-text('Export/Archive Course'), "
        "a[href*='exportCourse']"
    )
    if not export_link:
        return False

    export_link.click()
    page.wait_for_timeout(3000)

    # Select all content for export
    _select_all_content(page)

    # Submit the export
    submit_btn = page.query_selector(
        "input[type='submit'][value*='Export'], "
        "button:has-text('Export'), "
        "input[name='bottom_Submit']"
    )
    if submit_btn:
        submit_btn.click()
        page.wait_for_timeout(5000)

    return _download_export_file(page, unit_code, output_dir, timeout)


def _select_all_content(page: Page) -> None:
    """Select all content checkboxes in the export form."""
    # Check "Select All" if present
    select_all = page.query_selector(
        "input[type='checkbox'][id*='selectAll'], "
        "input[type='checkbox'][name*='selectAll'], "
        "a:has-text('Select All'), "
        "label:has-text('Select All')"
    )
    if select_all:
        tag = select_all.evaluate("el => el.tagName.toLowerCase()")
        if tag == "input":
            select_all.check()
        else:
            select_all.click()
        page.wait_for_timeout(1000)
        return

    # Otherwise check all individual content checkboxes
    checkboxes = page.query_selector_all(
        "input[type='checkbox'][name*='content'], "
        "input[type='checkbox'][id*='content']"
    )
    for cb in checkboxes:
        if not cb.is_checked():
            cb.check()


def _download_export_file(
    page: Page, unit_code: str, output_dir: Path, timeout: int
) -> bool:
    """Wait for the export to be ready and download it.

    Blackboard may show a processing page, then a download link.
    """
    # Wait for export to complete — Blackboard shows a status or download link
    max_polls = 12
    for attempt in range(max_polls):
        # Check for a download link
        download_link = page.query_selector(
            "a[href*='export'], "
            "a[href*='download'], "
            "a[href*='.zip'], "
            "a:has-text('Download')"
        )

        if download_link:
            print("  Downloading export...")
            try:
                with page.expect_download(timeout=timeout) as download_info:
                    download_link.click()
                download = download_info.value

                filename = download.suggested_filename or f"{unit_code}_export.zip"
                # Ensure unit code is in filename for skip-detection
                if unit_code and unit_code not in filename.upper():
                    stem = Path(filename).stem
                    filename = f"{unit_code}_{stem}.zip"

                dest = output_dir / filename
                download.save_as(dest)
                print(f"  Saved: {dest}")
                return True
            except PlaywrightTimeout:
                print("  Download timed out, retrying...")

        # Check if still processing
        processing = page.query_selector(
            ":has-text('processing'), :has-text('Building'), :has-text('queued')"
        )
        if processing or attempt < max_polls - 1:
            print(f"  Export in progress... (attempt {attempt + 1}/{max_polls})")
            page.wait_for_timeout(10000)
            page.reload(wait_until="networkidle", timeout=timeout)
        else:
            break

    return False
