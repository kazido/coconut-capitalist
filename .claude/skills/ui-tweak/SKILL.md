---
name: ui-tweak
description: Make a small change to a Coconut Capitalist screen (remove/move a button, fold a page into a tab or dropdown, reword a label, reorder rows) and fix the tests that pinned the old UI. Use for any "change this button/page/label" request.
---

# Tweak a screen

1. Find it: `grep -rn "<visible label>" cococap/screens cococap/ui`. Read only the screen class and the handler you change.
   Rules never go in screens: a new rule goes in `cococap/services/` first.
2. Keep it uncluttered (the owner dislikes clutter): fewer buttons, variants in a dropdown, one concept per page.
   A new page goes into an existing page as a tab (`cococap/ui/tabs.py`, `TabsScreen`; see `screens/player.py`), not a new registered screen.
3. Icons: message text and `emoji=` use `emojis.icon("<name>", "<plain glyph>")` / `emojis.ui(...)`, never a bare unicode emoji.
   Button labels and select text stay plain text (custom emoji do not render there). Currency: `emojis.bits(n)` etc.
4. Removing a button or page: also remove its dead handler, settings and links (`grep -rn "<handler or screen id>"`).
5. Tests that pinned the old UI: `grep -rln "<old label or word>" tests`. Make them assert on structure or a stable word, not a sentence.
   Helpers in `tests/test_hub.py`: `hub(...)`, `click(nav, inter, "Label")`, `find_button`, `select_named`, `all_text(nav)`, `buttons`.
6. `python -m scripts.quick_tests` (covers the layout-limit test in `tests/test_hub.py` when screens change) and ruff, then commit
   (`<Page>: what the player now sees`).
