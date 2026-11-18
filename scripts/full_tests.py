"""Run the whole test suite and ruff, and print only the failures and the two summary lines.

    .venv/Scripts/python.exe -m scripts.full_tests

The same short text is written to .full_tests_last.txt (git-ignored) so it can be read back later.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / ".full_tests_last.txt"


def run(cmd: list[str]) -> tuple[int, list[str]]:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode, [line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    py_code, py_lines = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line", "tests"])
    ruff_code, ruff_lines = run([sys.executable, "-m", "ruff", "check", "."])

    report: list[str] = [line for line in py_lines if line.startswith("FAILED")]
    if py_lines:
        report.append(py_lines[-1])  # pytest's final summary line
    if ruff_lines:
        report.append(ruff_lines[-1])  # ruff's last line, e.g. "All checks passed!"

    text = "\n".join(report) + "\n"
    print(text, end="")
    OUT_FILE.write_text(text, encoding="utf-8")
    return 1 if (py_code != 0 or ruff_code != 0) else 0


if __name__ == "__main__":
    sys.exit(main())
