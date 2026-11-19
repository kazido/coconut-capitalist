---
name: tidy-docs
description: Clean up Coconut Capitalist's docs after work lands: delete finished plans and empty idea lists, trim docs/STATUS.md, fix links and DESIGN.md lines the work made wrong. Use after a merge, when the user says a plan or list is done, or when asked "what's next" and STATUS looks stale.
---

# Tidy the docs (cheap: never read DESIGN.md whole)

1. `cat docs/STATUS.md; ls docs/plans`. For each plan read only its `Status:` line and headings (`grep -n "^Status\|^#\|^- " file | head -30`).
2. Decide done-ness from git, not memory: `git log --oneline -15 -- <paths the plan names>` or `git log --oneline --grep "<keyword>"`.
   Ask the user only if a plan is half done and git does not say which half.
3. Per plan or list:
   - Fully done: `git rm` it. Partly done: delete the done lines, keep the open ones, update `Status:`.
   - An idea list (`notes-*.md`, `*-tomorrow.md`) with no open lines left: delete the FILE, not just its lines.
4. `docs/STATUS.md`: remove the line of every deleted plan, reword lines that changed, update the "Last pruned" date. No changelog.
5. Dangling links: `grep -rn "<deleted file name>" docs CLAUDE.md .claude` and fix each hit.
6. If the work changed how a system behaves: `grep -n "^#" docs/DESIGN.md | grep -i <system>`, Read only that section, fix the wrong lines.
7. Commit (`Docs: ...`, say which plans were deleted and why). Docs-only changes need no tests.
