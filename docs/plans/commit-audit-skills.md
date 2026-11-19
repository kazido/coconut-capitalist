Status: NOT started (next up, agreed with the user on 2026-11-18)

# Commit-history audit -> skills that make updating the bot easier

## Goal
1. A short audit of the git history: find the kinds of changes the user keeps asking for (renames, balance tweaks, icon swaps,
   label fixes, tests updated for config numbers, uploads, landing a branch...). Output: a ranked list of recurring request types
   with 1-2 example commits each.
2. Turn the top recurring ones into Claude skills in `.claude/skills/<name>/SKILL.md` (short, token-cheap, like `add-item`,
   `make-emoji`), so each kind of update is one well-defined procedure. Show the user the list and get approval before writing them.

## How (cheap)
- Delegate the scan to a Haiku Explore agent: `git log --oneline` (all of it) + `git log --format='%s%n%b' -n 300`, group by request
  type, count, return a table under 40 lines. Do not read diffs unless a type is unclear.
- Existing skills to reuse/extend, not duplicate: add-item, art-review, balance-check, finish-feature, make-emoji.
- Lead (Opus) designs each skill; a Sonnet worker may write drafts; lead reviews and commits.

## Done when
The user approved the list, the new skills are committed, and this file is deleted (with its STATUS.md line).
