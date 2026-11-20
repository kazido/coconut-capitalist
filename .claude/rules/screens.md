---
paths:
  - "cococap/screens/**"
  - "cococap/ui/**"
  - "cococap/exts/**"
  - "tests/test_hub.py"
---

# Screens and UI

- **A new feature goes into an existing page as a tab or dropdown, not a new screen** (`cococap/ui/tabs.py`: `TabsScreen` hosts
  unregistered `Screen` panes behind one dropdown; open a tab with `go(i, "page", tab="x")`; see `screens/player.py`). Only add a
  registered screen for a genuinely new top-level area. Small screen changes: use the `ui-tweak` skill.
- **A new screen**: subclass `Screen` in `cococap/screens/`, set `id/label/emoji/description/links`, import it in `screens/__init__.py`,
  link it from Home/More/another screen. `tests/test_hub.py::test_every_screen_renders_valid_layout_within_discord_limits` covers layout limits.
- Keep screens uncluttered (the user dislikes clutter): fewer buttons, dropdowns for variants, one concept per page.
- Abbreviate tiers as TX everywhere and omit rarity names from item labels, e.g. display 'Base Part (T1)'.
- Show an emoji on every dropdown option whenever one applies to that option.
- Errors the player should see are `GameRuleError`s (`cococap/errors.py`); anything else is a bug and is not leaked to the player.
- UI tests drive screens with fake interactions: helpers in `tests/test_hub.py` (`hub("screen_id", **state)`, `click(nav, inter, "Label")`,
  `find_button`, `select_named`, `choose`, `all_text(nav)`, `buttons`). Assert on structure or a stable word, not a whole sentence.
