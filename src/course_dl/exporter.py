"""Blackboard course export download logic."""

from __future__ import annotations

import re
from pathlib import Path

from InquirerPy import inquirer
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from rapidfuzz import fuzz


def get_available_courses(page: Page, timeout: int = 60000) -> list[dict[str, str]]:
    """Get list of courses available in Blackboard.

    Returns list of dicts with keys: 'name', 'url'.
    """
    print("Fetching course list...")
    page.wait_for_timeout(3000)

    courses: list[dict[str, str]] = []

    # Navigate to the courses page
    courses_url = "https://lms.curtin.edu.au/ultra/course"
    page.goto(courses_url, wait_until="networkidle", timeout=timeout)
    page.wait_for_timeout(3000)

    # Look for course links — Blackboard Ultra uses course card links
    course_links = page.query_selector_all("a[href*='/ultra/courses/']")

    if not course_links:
        # Fallback: try the classic Blackboard course list
        course_links = page.query_selector_all(
            "a[href*='/webapps/blackboard/execute/courseMain']"
        )

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
        courses.append({"name": name, "url": href})

    print(f"  Found {len(courses)} courses")
    return courses


def fuzzy_match_courses(
    available: list[dict[str, str]],
    search_terms: list[str],
    threshold: int = 60,
) -> list[dict[str, str]]:
    """Match courses using fuzzy string matching against search terms.

    Each search term is compared against each course name. A course is
    included if any term scores above the threshold. Uses token_set_ratio
    so word order and extra words in the title don't penalise matches.
    """
    matched: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for term in search_terms:
        best_score = 0
        best_course: dict[str, str] | None = None

        for course in available:
            name = course["name"]
            # Use token_set_ratio — handles partial matches well
            score = fuzz.token_set_ratio(term.lower(), name.lower())
            # Also try straight partial_ratio for short terms like "COMP1000"
            partial = fuzz.partial_ratio(term.lower(), name.lower())
            final_score = max(score, partial)

            if final_score > best_score:
                best_score = final_score
                best_course = course

        if best_course and best_score >= threshold and best_course["url"] not in seen_urls:
            print(f"  '{term}' -> {best_course['name']} (score: {best_score})")
            matched.append(best_course)
            seen_urls.add(best_course["url"])
        else:
            print(f"  '{term}' -> no match (best score: {best_score}, threshold: {threshold})")

    return matched


def interactive_pick(available: list[dict[str, str]]) -> list[dict[str, str]]:
    """Show an interactive checkbox picker for course selection.

    Arrow keys to move, space to toggle, enter to confirm.
    """
    if not available:
        return []

    choices = [{"name": c["name"], "value": i} for i, c in enumerate(available)]

    selected = inquirer.checkbox(
        message="Select courses to export (space to toggle, enter to confirm):",
        choices=choices,
    ).execute()

    return [available[i] for i in selected]


def already_downloaded(course_name: str, output_dir: Path) -> bool:
    """Check if a course export already exists based on the course name."""
    if not output_dir.exists():
        return False
    # Build a simplified key from the course name for comparison
    key = _sanitise_name(course_name)
    for f in output_dir.iterdir():
        if f.suffix == ".zip" and key in _sanitise_name(f.name):
            return True
    return False


def _sanitise_name(name: str) -> str:
    """Lowercase and strip non-alphanumeric chars for loose comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def export_courses(
    page: Page,
    search_terms: list[str] | None,
    output_dir: Path,
    download_all: bool = False,
    overwrite: bool = False,
    match_threshold: int = 60,
    timeout: int = 60000,
) -> dict[str, str]:
    """Export and download courses from Blackboard.

    Returns a dict of {course_name: status} where status is 'ok',
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
    for i, c in enumerate(available, 1):
        print(f"  {i}. {c['name']}")

    # Determine which courses to export
    if download_all:
        targets = available
    elif search_terms:
        print(f"\nMatching search terms (threshold: {match_threshold})...")
        targets = fuzzy_match_courses(available, search_terms, match_threshold)
        if not targets:
            print("  No courses matched. Try lowering --match-threshold or omit search "
                  "terms for interactive picker.")
            return results
    else:
        # Interactive picker
        print()
        targets = interactive_pick(available)
        if not targets:
            print("  No courses selected.")
            return results

    print(f"\nWill export {len(targets)} course(s):")
    for c in targets:
        print(f"  - {c['name']}")

    for course in targets:
        label = course["name"]
        print(f"\n--- {label} ---")

        # Skip check
        if not overwrite and already_downloaded(label, output_dir):
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
    course_name = course["name"]
    course_url = course["url"]

    # Make URL absolute if needed
    if course_url.startswith("/"):
        course_url = f"https://lms.curtin.edu.au{course_url}"

    # Navigate to the course
    print(f"  Opening course: {course_name}")
    page.goto(course_url, wait_until="networkidle", timeout=timeout)
    page.wait_for_timeout(3000)

    # Try Ultra flow first, then Classic
    if _try_ultra_export(page, course_name, output_dir, timeout):
        return

    if _try_classic_export(page, course_name, output_dir, timeout):
        return

    raise RuntimeError(
        f"Could not find export option for {course_name}. "
        "Run with --visible to debug."
    )


def _try_ultra_export(
    page: Page, course_name: str, output_dir: Path, timeout: int
) -> bool:
    """Attempt Blackboard Ultra export flow."""
    settings_btn = page.query_selector(
        "[data-ng-click*='settings'], "
        "button[aria-label*='Settings'], "
        "button[aria-label*='Course settings'], "
        "a[href*='settings']"
    )
    if not settings_btn:
        settings_btn = page.query_selector(
            "button[aria-label*='More options'], "
            "button[aria-label*='Course management']"
        )

    if not settings_btn:
        return False

    settings_btn.click()
    page.wait_for_timeout(2000)

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

    _select_all_content(page)

    submit_btn = page.query_selector(
        "button:has-text('Export'), "
        "input[type='submit'][value*='Export'], "
        "button[type='submit']"
    )
    if submit_btn:
        submit_btn.click()
        page.wait_for_timeout(5000)

    return _download_export_file(page, course_name, output_dir, timeout)


def _try_classic_export(
    page: Page, course_name: str, output_dir: Path, timeout: int
) -> bool:
    """Attempt Classic Blackboard export flow."""
    control_panel = page.query_selector(
        "#controlPanel, "
        "a:has-text('Control Panel'), "
        "a:has-text('Course Management'), "
        "#courseMenuPalette_contents a:has-text('Packages'), "
        "a[href*='exportCourse'], "
        "a[href*='export']"
    )

    if not control_panel:
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

    _select_all_content(page)

    submit_btn = page.query_selector(
        "input[type='submit'][value*='Export'], "
        "button:has-text('Export'), "
        "input[name='bottom_Submit']"
    )
    if submit_btn:
        submit_btn.click()
        page.wait_for_timeout(5000)

    return _download_export_file(page, course_name, output_dir, timeout)


def _select_all_content(page: Page) -> None:
    """Select all content checkboxes in the export form."""
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

    checkboxes = page.query_selector_all(
        "input[type='checkbox'][name*='content'], "
        "input[type='checkbox'][id*='content']"
    )
    for cb in checkboxes:
        if not cb.is_checked():
            cb.check()


def _download_export_file(
    page: Page, course_name: str, output_dir: Path, timeout: int
) -> bool:
    """Wait for the export to be ready and download it."""
    max_polls = 12
    for attempt in range(max_polls):
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

                filename = download.suggested_filename or f"{_sanitise_name(course_name)}.zip"
                dest = output_dir / filename
                download.save_as(dest)
                print(f"  Saved: {dest}")
                return True
            except PlaywrightTimeout:
                print("  Download timed out, retrying...")

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
