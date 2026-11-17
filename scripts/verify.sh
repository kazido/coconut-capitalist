#!/usr/bin/env bash
# The objective "done" check for any agent (local or cloud): lint + the tests that matter for what changed.
#
#   scripts/verify.sh                      # tests chosen from the files you changed (git diff + new files)
#   scripts/verify.sh tests/test_foo.py    # exactly these tests
#
# Prints VERIFY PASSED or VERIFY FAILED as its last line and exits 0 / 1. It never runs the whole suite (slow); ask for that
# explicitly with `scripts/verify.sh --all`.
set -u
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

if [ "${1:-}" = "--all" ]; then
  tests=("tests")
elif [ "$#" -gt 0 ]; then
  tests=("$@")
else
  # (VERIFY_CHANGED overrides the file list: handy for trying the mapping, e.g. VERIFY_CHANGED="cococap/services/mining.py")
  changed="${VERIFY_CHANGED:-$( (git diff --name-only HEAD; git ls-files --others --exclude-standard) | sort -u)}"
  tests=()
  add() { for f in "$@"; do if [ -e "$f" ]; then tests+=("$f"); fi; done; }
  while IFS= read -r f; do
    case "$f" in
      tests/test_*.py) add "$f" ;;
      cococap/services/*.py) b=$(basename "$f" .py); add tests/test_"$b"*.py ;;
      cococap/screens/*.py) b=$(basename "$f" .py); add tests/test_"$b"*.py tests/test_hub.py ;;
      cococap/registry/*.py|configs/*.toml) add tests/test_registry.py tests/test_economy_guard.py ;;
      cococap/ui/*.py) add tests/test_hub.py tests/test_reward_screen.py ;;
      art/*) add tests/test_art.py ;;
    esac
  done <<< "$(printf "%s\n" $changed)"
  uniq=()
  for t in ${tests[@]+"${tests[@]}"}; do
    case " ${uniq[*]-} " in *" $t "*) ;; *) uniq+=("$t") ;; esac
  done
  tests=(${uniq[@]+"${uniq[@]}"})
  [ "${#tests[@]}" -eq 0 ] && tests=(tests/test_registry.py)
fi

echo "== ruff =="
if ! "$PY" -m ruff check . ; then echo "VERIFY FAILED (ruff)"; exit 1; fi
echo "== tests: ${tests[*]} =="
if ! "$PY" -m pytest -q "${tests[@]}" ; then echo "VERIFY FAILED (tests)"; exit 1; fi
echo "VERIFY PASSED"
