# course-dl

Download Blackboard course exports from Curtin University's LMS as Common Cartridge
packages, useful for migrating courses to Canvas or other LMS platforms.

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

Exporting is a **two-step process** because Blackboard takes 15–30 minutes to
build each Common Cartridge package.

### Step 1: Trigger builds

```bash
# Trigger builds for specific courses (fuzzy-matched)
course-dl build COMP1000 "Data Structures"

# Trigger builds for all courses
course-dl build --all

# Interactive picker — no args, select from a list
course-dl build
```

Blackboard queues the export and confirms with "This action has been queued."
You can trigger builds for many courses at once — they build in parallel on the
server.

### Step 2: Download packages

Wait 15–30 minutes, then download with the **same search terms**:

```bash
# Download matching courses
course-dl download COMP1000 "Data Structures"

# Download all
course-dl download --all

# Interactive picker
course-dl download
```

Courses with no package ready yet will show "not ready" — just run the command
again later.

### Typical batch workflow

```bash
# 1. Trigger all builds
course-dl build --all

# 2. Wait 15-30 minutes...

# 3. Download everything
course-dl download --all -o exports/
```

### Common options

```
course-dl [OPTIONS] {build,download}

Options (before subcommand):
  -u, --username STR    Curtin username
  -p, --password STR    Curtin password
  --visible             Show the browser window (default: headless)
  --timeout INT         Navigation timeout in ms (default: 60000)

Subcommand options:
  SEARCH...             Search terms (fuzzy-matched against course titles)
  -f, --file PATH       File with search terms (one per line)
  --all                 Select all courses
  --match-threshold INT Fuzzy match score 0-100 (default: 60)

Download-only options:
  -o, --output-dir PATH Output directory (default: ./exports/)
  --overwrite           Re-download courses that already exist locally
```

### Fuzzy matching

Course titles in Blackboard are long. You don't need the full title:

```bash
course-dl build COMP1000              # matches by unit code
course-dl build "Unix and C"          # matches by partial name
course-dl build "Data Structures"     # matches by topic
```

### Interactive picker

When no search terms are provided, an interactive checkbox list is shown.
Use arrow keys to move, space to toggle, enter to confirm.

### Skip behaviour

`course-dl download` skips courses that already have a `.zip` or `.imscc` file
in the output directory matching the unit code. Use `--overwrite` to force
re-download.

When only one package exists on Blackboard, it is deleted after download
(since we created it). When multiple packages exist, none are deleted and the
tool logs which one was downloaded.

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
