# Batch 2, plans 1 and 2: thumbnails, then buy/sell lists

Context: items and pets now have pixel-art application emoji. Inline emoji are tiny, so big art is wanted on item-focused screens.
The `ideas` file adds: a big thumbnail on each item's Wiki page. Also HANDOFF #8: buy/sell menus should be a markdown list + one dropdown + one button.
(On execution: copy each plan to `docs/plans/` and tick it off in HANDOFF #8. Remaining Batch 2 items stay queued: live refresh, fishing rework, starred materials, art for species/enchants/UI/mine types, weak-art redo, markdown/spoiler/radio-modal.)

## Plan 1: Thumbnails

**Approach: use the emoji's own CDN image, no file hosting.** `art/out` is git-ignored and not on the host, and Components V2 `ui.Thumbnail` / `Section(accessory=...)` needs a URL or an `attachment://` file. Application emoji have a CDN URL (`https://cdn.discordapp.com/emojis/<id>.png|gif?size=128&quality=lossless`), so no attachment plumbing in `nav.py` (it only does `edit_message(view=...)`, nav.py:188).

1. `cococap/emojis.py`: keep the emoji id/animated flag next to the mention string (`load()` already receives objects with `.name`; store `.id`, `.animated`). Add `image_url(kind, id, size=128) -> str | None` (None when the emoji isn't uploaded, so tests/offline fall back to no thumbnail). Reuse `for_id`'s name logic (`name_for`, the `ALIASES` fallback).
2. `cococap/ui/components.py`: add `thumb(url)` wrapper over `ui.Thumbnail`, and `section_art(markdown, url)` that returns a `Section` with the thumbnail accessory when `url` exists, else a plain `text`.
3. Screens (each is a few lines):
   - Wiki item page (`screens/wiki.py:60`, the `item_attributes` text block) = the `ideas` request.
   - Item/shop rows in the shop screen: handled in Plan 2 (the single selected item gets the big art).
   - Reward / Result screen and rare-drop banner page (`ui/flair.py`, Result in `ui/nav.py:50`): thumbnail of the top drop (rarest item) on the first `lines` block.
4. Pets and other kinds (`pet_`, `species_`) reuse `image_url`; wire pet page only if it is a one-line change.

Tests: `tests/test_emojis.py` (image_url present/absent, animated gif vs png, alias); `tests/test_hub.py::test_every_screen_renders_valid_layout_within_discord_limits` covers layout. Add one hub test that the wiki item page contains a Thumbnail when an emoji is loaded.

Open risk: Discord scales the CDN image smoothly, so tiny pixel art may look soft. Verify on a real server after restart; fallback is to bake 128px NEAREST upscales and upload them as extra application emoji (`<id>_big`), still no hosting.

## Plan 2: Buy/sell as a list

Today `ShopScreen.build` (`screens/shop.py:44-80`) renders one `section` per item, each with its own Buy/Sell button (PER_PAGE rows of buttons).

New layout, buy and sell modes alike:
- One text block: a markdown list of the page's items (`emoji name  ·  price/count  ·  sell-all value`), with the selected item bolded/marked.
- One `select` (items on this page, option emoji, price in the description) -> sets `self.selected`.
- Below it, a section for the selected item: big art thumbnail (Plan 1), its description, and **one** button (Buy / Sell) that calls the existing `_ask_quantity(item.id, mode, qty)` unchanged.
- Keep mode toggle, category buttons and pagination as is. Default `selected` = first item of the page; reset it on mode/category/page change; clear it if the item disappears after a sale.
- Reuse the same list+select+button helper for `screens/market.py` only if it has per-row buttons (it appears not to: it has Sell all / Deposit only), so likely no change there.

Tests (`tests/test_hub.py` helpers: `hub`, `click`, `select_named`, `all_text`): select an item then click Buy -> quantity modal for that item; button count on the page no longer grows with item count; sell mode shows the per-item total; selection resets on mode change. Assert on structure, not whole sentences.

## Order and verification
Plan 1 steps 1-2 first (shared pieces), then Plan 2 (uses the thumbnail), then Plan 1 step 3 screens. Small enough to hand to `worker` in two briefs (emojis+components; shop screen) with `tester` after.
Run: `tests/test_emojis.py`, `tests/test_hub.py`, `ruff check .`. Not verifiable without a live bot: how the thumbnails look in Discord (restart the bot and check the wiki item page, shop, and a reward screen).
