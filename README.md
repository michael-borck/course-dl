# course-dl

Download Blackboard course exports from Curtin University's LMS.

## Installation

```bash
uv tool install course-dl
playwright install chromium
```

Or install from source:

```bash
git clone https://github.com/michael-borck/course-dl.git
cd course-dl
uv sync
uv run playwright install chromium
```

## Usage

### Basic usage

```bash
# Search by unit code (fuzzy matched against course titles)
course-dl COMP1000 ISAD1000

# Search by partial name
course-dl "Data Structures" "Linear Algebra"

# Mix codes and names
course-dl COMP1000 "Application Development"

# Interactive picker — no args, just select from a list
course-dl

# Export all available courses
course-dl --all
```

### Options

```
course-dl [SEARCH...] [OPTIONS]

Positional:
  SEARCH                Search terms to fuzzy-match against course titles.
                        If omitted, an interactive picker is shown.

Options:
  -f, --file PATH       File with search terms (one per line or comma-separated)
  -u, --username STR    Curtin username
  -p, --password STR    Curtin password
  -o, --output-dir PATH Output directory (default: ./exports/)
  --all                 Download all courses visible in Blackboard
  --overwrite           Re-download courses that already exist locally
  --match-threshold INT Fuzzy match score 0-100 (default: 60)
  --visible             Show the browser window (default: headless)
  --timeout INT         Navigation timeout in ms (default: 60000)
```

### Fuzzy matching

Course titles in Blackboard are often long and include extra metadata
(e.g. `COMP1000 - Unix and C Programming - S1 2026 - Bentley (AUTO_CREATED_123)`).
You don't need the full title — just provide enough to uniquely identify it:

```bash
course-dl COMP1000              # matches by unit code anywhere in title
course-dl "Unix and C"          # matches by partial name
course-dl "Data Structures"     # matches by topic
```

Adjust `--match-threshold` (default 60) if matches are too loose or too strict.

### Interactive picker

When no search terms are provided, an interactive checkbox list is shown
after login. Use arrow keys to move, space to toggle selection, and
enter to confirm.

### Skip / overwrite behaviour

By default, `course-dl` skips courses that already have a `.zip` file in the
output directory matching the course name. Use `--overwrite` to force re-download.

## Credentials

Credentials are resolved in order:

1. CLI flags (`-u`, `-p`)
2. Environment variables (`CDL_USERNAME`, `CDL_PASSWORD`)
3. `.env` file (searched in order):
   - `~/.config/course-dl/.env`
   - `~/.course-dl.env`
   - `./.env`
4. Interactive prompt

Copy `.env.example` to one of the above locations:

```bash
cp .env.example ~/.config/course-dl/.env
```

## License

MIT
