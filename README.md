# course-dl

Download Blackboard course exports from Curtin University's LMS.

## Installation

```bash
uv tool install course-dl
playwright install chromium
```

Or install from source:

```bash
git clone https://github.com/michaelborck/unit-dl.git
cd unit-dl
uv sync
uv run playwright install chromium
```

## Usage

### Basic usage

```bash
# Export specific units
course-dl COMP1000 ISAD1000

# Export units from a file
course-dl -f units.txt

# Export all available courses
course-dl --all
```

### Options

```
course-dl [UNITS...] [OPTIONS]

Positional:
  UNITS                 Unit codes (e.g. COMP1000 ISAD1000)

Options:
  -f, --file PATH       File with unit codes (newline or comma-separated)
  -u, --username STR    Curtin username
  -p, --password STR    Curtin password
  -o, --output-dir PATH Output directory (default: ./exports/)
  --all                 Download all courses visible in Blackboard
  --overwrite           Re-download courses that already exist locally
  --visible             Show the browser window (default: headless)
  --timeout INT         Navigation timeout in ms (default: 60000)
```

### Skip / overwrite behaviour

By default, `course-dl` skips courses that already have a `.zip` file in the output directory matching the unit code. Use `--overwrite` to force re-download.

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
