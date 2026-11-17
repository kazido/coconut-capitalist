# Brief NNN: <one-line title>

Plan: `docs/plans/NNN-name.md` (step N of M) · Executor: read `docs/EXECUTOR.md` first.

## Goal
One or two sentences: what should be true when this is done, in player terms if it is gameplay.

## Files you may touch
- `path/one.py`: what changes here
- `tests/test_one.py`: add the tests below

(Everything else is off limits. If you need another file, stop and say why.)

## Reuse, do not reinvent
- `cococap/services/example.py::function`: why it applies
- `cococap/screens/example.py`: a screen to copy the layout from

## Behaviour (be exact)
1. When X, then Y (with the actual numbers or config keys).
2. Edge case: ...
3. Config: key `[section] name = value` in `configs/xxx.toml` (validated by `cococap/registry/models.py::Model`).

## Tests that prove it
- `test_name_one`: arrange / act / assert in one line each, and the exact expected value.
- `test_name_two`: ...

## Done means
- `scripts/verify.sh` prints `VERIFY PASSED`.
- One commit. Message: `<what and why>` and the line `Co-Authored-By: <the model that wrote it>`.

## Do not
- Do not run the full test suite, add dependencies, or edit files outside the list above.
- (Add the specific traps for this task: e.g. "the registry is frozen: build copies with `model_copy(update=...)`".)

## Attempt log (the planner fills this in after each round)
- Attempt 1: <result, what was wrong, what to do differently>
