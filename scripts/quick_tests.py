"""Run only the tests related to the files changed since HEAD. Prints very little, to save tokens.

    .venv/Scripts/python.exe -m scripts.quick_tests

Changed test files run themselves. Other changed .py/.toml files run every test whose text mentions their file name
(e.g. configs/foraging.toml -> tests that mention "foraging"). Very generic names match almost every test, so they only
run the registry tests. Full suite: `python -m scripts.full_tests`.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_FILES = 12  # keeps a quick run quick; anything beyond this is reported as skipped
IGNORED_DIRS = ("art/", "docs/", "data/")
GENERIC_STEMS = {"__init__", "models", "loader", "items", "economy"}  # match nearly every test, so not useful
FALLBACK_TEST = "tests/test_registry.py"


def select_tests(changed: list[str], tests_dir: Path) -> tuple[list[str], list[str]]:
    """Return (test files to run, notes). Paths are relative to the repo root, with forward slashes."""
    chosen: list[str] = []
    notes: list[str] = []

    def add(path: str) -> None:
        if path not in chosen:
            chosen.append(path)

    all_tests = sorted(tests_dir.glob("test_*.py"))
    for raw in changed:
        path = raw.replace("\\", "/")
        if path.startswith(IGNORED_DIRS) or not path.endswith((".py", ".toml")):
            continue
        name = Path(path).name
        # A changed test file is its own test: no need to search for it.
        if path.startswith("tests/") and name.startswith("test_") and name.endswith(".py"):
            add(path)
            continue
        stem = Path(path).stem
        if stem in GENERIC_STEMS:
            notes.append(f"generic name '{stem}': running only {FALLBACK_TEST}")
            add(FALLBACK_TEST)
            continue
        # Whole-word match, so 'fish' does not pick up 'fishing' tests.
        pattern = re.compile(rf"\b{re.escape(stem)}\b", re.IGNORECASE)
        for test in all_tests:
            text = test.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(text):
                add(f"tests/{test.name}")

    if len(chosen) > MAX_FILES:
        notes.append(f"skipped {len(chosen) - MAX_FILES} test files (cap {MAX_FILES})")
        chosen = chosen[:MAX_FILES]
    return chosen, notes


def changed_files() -> list[str]:
    """Tracked changes since HEAD plus untracked files that are not ignored by git."""
    out: list[str] = []
    for args in (["git", "diff", "--name-only", "HEAD"], ["git", "ls-files", "--others", "--exclude-standard"]):
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out.extend(line.strip() for line in result.stdout.splitlines() if line.strip())
    return out


def main() -> int:
    chosen, notes = select_tests(changed_files(), ROOT / "tests")
    for note in notes:
        print(note)
    if not chosen:
        print("no related tests")
        return 0

    print("testing: " + " ".join(chosen))
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line", *chosen]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("FAILED"):
            print(line)
    if lines:
        print(lines[-1])  # pytest's final summary line
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
