---
name: prepare-clear
description: Get a chat ready for /clear: write the progress so far into the active plan (docs/plans/<plan>.md) and STATUS.md, commit it, and tell the user what the next chat should start with. Use when the user says they will clear the chat, asks to "update the plan so far", or types /prepare-clear.
---

# Prepare for /clear (cheap: write only what the next chat needs)

The next chat starts cold: it knows only CLAUDE.md, memory and what you write now. Put the handoff in the plan file, not in chat.

1. **Find the plan.** The one this chat worked on (`docs/plans/<name>.md`). If none exists and the work is multi-step, create one with a `Status:` line.
2. **Update its `Status:` line**: which steps are done, on which branch, and the next step by number and name.
3. **Add or refresh a `## Built so far` section** (replace the old one, never append a second). Keep it under ~25 lines:
   - Commits per step (short hash) and the branch; say plainly if it is NOT merged to master yet.
   - Decisions the user made in this chat that are not written elsewhere in the plan (one line each).
   - The key names the next step builds on: functions, config tables, screens, with file paths. Names, not explanations.
   - Test files that cover the work.
   - Open notes: TODO(balance) guesses, missing art, flaky or unverified things, docs not yet written, anything skipped.
   No history, no narration, no pasted code.
4. **Fix any plan line the work made wrong** (e.g. a step that landed differently than planned).
5. **Update the plan's line in `docs/STATUS.md`** (one line: what is built, what is next).
6. **Commit** both files on the branch the work is on (`Plan: <name> progress notes (...)`), with the attribution line.
7. **Reply in 3-5 lines**: what you wrote, where, the branch/folder the next chat must run in, and the next step. Do not recap the whole session.

Do not start the next step. Do not merge or push.
