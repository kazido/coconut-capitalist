Status: BUILT and on master except: (a) the big Pillow tool picture on the Tools detail page + cosmetics (step 9, next, owner said hold until usage resets), (b) step 10 docs. Part tier = rarity (1 Common .. 8 Celestial), shops never sell tier 7-8.

# Tools rework: generic parts + Smithing (replaces the upgrade ladder)

## Context
Tools are linear today: a free starter per skill, 3 plain upgrades, then a fork into 2 paths (`configs/items.toml` `.tool.upgrade`/`.fork`,
`services/upgrades.py`, `configs/tools.toml` power curves + path stats). Nearly every player's tool is identical, which is boring, and the
owner wants a player shop later where cool tools are worth selling. Goal: every tool is a unique combination of dropped parts and traits,
built through a new light Smithing skill, and old tools are tradeable/salvageable so used tools have value. The player shop itself is a later plan.

Owner's decisions (interview, 2026-11-19):
- **Parts are generic and drop from all skills.** Three part types, all required: a tool = **1 Base + 1 Trim + 1 Accent**
  (changed 2026-11-19, was primary + 2 secondaries). You pick the tool kind (pickaxe/rod/axe/can) when smithing. Base = the working end
  (pick head, axe blade, rod reel, can body), Trim = what you hold (handle, pole), Accent = a wrap, line or spout.
- **No tool tiers. Power = sum of the parts' power.** Each part has a tier; a higher tier part grants more power. **All three part
  types are equal** (same power per tier; decided 2026-11-19), so any part is as valuable as another.
  Max tool = 3 high-tier parts with the traits you want; a 3+3+1 is a fine starter build.
- **Part tier is random by rarity, weighted by area.** Higher areas make high tiers more common. Hard cap: a player in area A can roll at most
  about tier A+2 (area 1 -> tier 3 at best, rarely). No lucky jackpots far above your area.
- **Traits.** Freshly dropped parts carry several traits; at smithing you **pick 3** for the tool (max 3 per tool), the rest are lost.
  **Part traits are GENERIC only** (any part can go into any tool kind): +power, +xp, +sell value and more generic ideas (TODO).
  Skill-specific bonuses (ore yield, rich lodes, less pressure, good chops, crop yield, fishing...) live on the skill accessories
  instead (decided 2026-11-19). The current trait list in `configs/smithing.toml` still has skill traits: retune it later.
- **Smithing roll** adds: a **quality grade** (Crude / Fine / Superb / Masterwork, scales power and trait numbers), a chance of a **bonus trait**
  only if fewer than 3 were picked, and a rare **cosmetic** (see Art).
- **Salvage.** You can break down a tool you did NOT smith (bought or traded). You get all 3 parts back, each with only the 1 trait the smith picked
  from it (a part with no picked trait comes back plain). So every tool records its original smith. Recycled parts are 1-trait, fresh drops are worth the most.
- **No wear.** Tools last forever.
- **Abilities come from enchants only, 1 enchant per tool.** Ability enchants stay (soloist, double_hook, iron_frame, double_strike, lure,
  steady_line, sharp_eye, seasoned, deepcall, seedkeeper, gleaner...). Stat enchants (keen, scholar, appraiser, veinfinder, bounty, fertile...)
  become traits. Future idea (NOT in this plan): a second ability via a high-level unlock or a special part.
- **Accessories: 2 slots per skill**, skill-specific, not smithed. Basic ones are bought in the Shop, rarer ones drop in that skill. Each
  rolls **skill-specific traits on drop** from their own pool (different from tool traits), so the two accessories pick a playstyle
  (e.g. mining: safe-and-steady vs. rich-lode gambler). Accessories are instances (like parts) and tradeable.
- **Smithing is a light skill** (more light skills come later): xp from smithing and salvaging; its level gates the highest part tier you can work and improves quality odds.
  No mastery tree, locations or shipments. Advanced smithing (a level unlock) = **swap one part** on a tool you own.
- **Old tools: reset, with starter parts.** Every existing tool instance is removed. Instead of refunding materials, players who had worked
  for a decent tool get **decent tool parts** to start with (tier and count scaled by how far up the old chain their tools were, fork tools
  best); everyone gets the free starters. Players are told through the new notifications (Part A).

## Art (decided first, 2026-11-19)
Two layers, so no tool combination ever needs its own drawing:
- **One colour per tier, shared by all parts** (`TIERS` in `art/gen/tool_layers.py`): 1 wood, 2 stone, 3 iron, 4 gold, 5 platinum,
  6 emerald/crystal, 7 void. A base 3 / trim 3 / accent 1 tool is an iron head, iron handle, wood wrap.
- **List emoji = kind + Base tier.** One hand-drawn sprite per kind (4, owner-approved; generator `art/gen/tool_layers.py`), all three layers
  coloured tier n = **28 generated emoji** (`tool_<kind>_t<n>`). Parts in lists: one sprite each for Base, Trim and Accent, tier-tinted the
  same way = **21 emoji** (`part_base_t<n>`, `part_trim_t<n>`, `part_accent_t<n>`).
- **Tool page image = rendered by Pillow at runtime**, shown big in the tool view (attachment in a Components V2 Thumbnail/MediaGallery). It is made
  of the 3 layers so you can see the parts, each in its own part's tier colour. Each kind is drawn once in these layers (letters P/H/A per
  pixel in the generator), which the bot recolours.
- **Cosmetics exist only in the image** (rendered, no extra emoji): rare named palettes (Obsidian, Frostforged, Sunsteel...) that override the
  layer palettes, backgrounds/frames (forge glow, starfield, gilded border), and effect overlays (sparkles, embers, frost, glow aura). Each is a small
  asset or a draw function; a tool stores e.g. `{"palette": "sunsteel", "frame": "gilded", "overlay": "embers"}`; most tools have none, rare ones
  have one, very rare ones stack. Not animated.
- **Runtime cost:** Pillow moves from the `art` extra to a real dependency. Images are rendered from a look key (kind, palettes, cosmetics) and
  cached on disk (`data/tool_images/<hash>.png`), so a tool is drawn once. A renderer lives in `cococap/art_runtime.py` (no discord), with tests
  that it renders every kind x cosmetic without error and stays small.

## Design (data first)
- `configs/smithing.toml` (new): part types (base, trim, accent), part tier table (power per tier, the same for every type), area weights per tier + the "area + 2" cap, trait pool
  (id, name, stat, amount per quality, which tool kinds it fits, how many traits a fresh part rolls by rarity), quality grades (odds by smithing
  level, multiplier), cosmetic chance, smithing xp, level gates (max part tier by level, part swap unlock level). Mark guesses `TODO(balance)`.
- Parts are **instances**, not stackable items (each has its own tier + traits): reuse `item_instances` (`ItemInstanceRow`, `cococap/db/tables.py:85`)
  with template ids `part_base` / `part_trim` / `part_accent`; `rolled = {"tier": n}`, plus a new JSON `traits` list.
- Tool instances gain columns: `smith_id` (original smith), `parts` (JSON: base, trim, accent, each with tier and
  the trait picked from it), `quality`, `cosmetic` (JSON look: palette/frame/overlay or empty). Tool templates collapse to one per kind (`tool_pickaxe`, `tool_rod`, `tool_axe`, `tool_can`; sword stays paused).
  Alembic migration 0011 adds the columns (`tests/test_db_migrations.py`).
- Stats: `services/equipment.effective_stats` (`equipment.py:37`) already merges template + rolled + enchants into stat names the engines read.
  Extend it: power = sum of part power x quality; traits add their stats; the single enchant adds its ability. Engines keep reading the same
  stat names (`power`, `scholar`, `appraise`, `rich_chance`, `ore_yield`, `crop_yield`, `danger_reduction`, `good_chop`...), so mining/fishing/
  foraging/farming need few or no changes. `services/tool_effects.power_stats` keeps the per-kind power curves; path multipliers go away (paths become traits).
- New `services/smithing.py` (no discord): `roll_part(user, area, rng)`, `smith(user, kind, part_ids, picked_traits, rng)`, `salvage(user, tool_id)`
  (refuses own-smithed tools), `swap_part(user, tool_id, which, part_id)` (level-gated). Errors as `GameRuleError`.
- Part drops: hook each skill's drop roll (where starred drops are rolled, `services/stars.py` callers) with a small part chance per action,
  tier from the area weights. One shared helper, so all four skills drop parts the same way.
- Enchanting (`services/enchanting.py`): one enchant per tool; applying a new one replaces the old (confirm in UI). Stat-enchant scrolls are retired
  (migration refunds them; see below).
- Accessories: instances with template ids from `configs/accessories.toml` (skill, base stats, trait count by rarity, per-skill trait pool);
  **2 equipped per skill** (`equip_accessory(user, skill, slot, id)`), stats merged in `equipped_stats` next to the tool. Basic ones in the
  Shop (fixed, no traits), rarer ones in each skill's drop table with rolled traits.
- **Light skills page:** the Skills page (`cococap/screens/skills.py`) becomes a `TabsScreen` with tabs Skills (the 4 now) and Light skills
  (Smithing now; a list driven by the registry so later light skills just appear). Light skills have level + xp only.
- UI (no new top-level screen): the **Tools page** (`screens/` tools tabs) gets tabs: Tools (equip, enchant), Smithing (pick kind -> pick a base, a trim
  and an accent -> pick up to 3 traits -> Smith), Parts (list with tier and traits), Salvage. Tool view: the rendered image, parts, traits,
  quality, smith, cosmetic.
  Remove the Upgrade tab.
- Reset migration (0012): for every player, score their old tools by chain position (plain step 1-3, fork, fork upgrades) and grant starter
  parts from a table in `smithing.toml` (`[[legacy_grant]]`: best old step -> e.g. a base, trim and accent of tier N with 1-2 traits);
  stat-enchant levels become bits; ability enchants come back as their scrolls. Delete the instances; every player gets the 4 free starters
  (base + trim + accent, plain tier 1, smith = the game, not salvageable). Back up `data/cococap.db` first. A notification explains it.

## Part A (build first, independent): player notifications + changelog
- **Notifications:** `configs/notices.toml` (or `docs/`-free data file) lists notices `{id, date, title, body}`; a player sees every notice
  they have not seen yet as a popup the first time they open `/play` (or any shortcut) after it ships (reuse `cococap/ui/popup.py`, as the
  level-up/rare-drop popups do). Seen ids are stored per player (settings JSON or a small table + migration). One popup lists several new
  notices if there are many (paged).
- **More page** (`cococap/screens/home.py` `MoreScreen`): two new buttons, **Messages** (all past notices, newest first) and **Changelog**.
  If the More page runs out of room, both go on one new "News" page with tabs (`TabsScreen`).
- **Changelog:** `configs/changelog.toml` (data, `[[entry]] {date, title, body, major}`), shown as paged text, newest first. Major entries
  (system reworks) get a full write-up; small buffs/adjustments are grouped into one short summary line per update.
- **Upkeep rule** (add to CLAUDE.md + `finish-feature` skill): any change players will notice gets a changelog entry; a change they may have
  questions about also gets a notice. Seed the changelog with the recent player-facing changes (wyrm tunnels, trade countdown, menus...).
- Tests: a new notice pops up once and never again; Messages and Changelog render within Discord limits and page correctly.

## Steps (each a commit; item-id removals land on master first and alone)
1. Plan doc in `docs/plans/tools-smithing.md` (this file, trimmed) + STATUS line.
1b. Art first: 4 layered base sprites (owner approves), the tier palettes, the 28 tool + 21 part emoji generated, and `cococap/art_runtime.py`
   rendering a tool image with 2-3 sample cosmetics; Pillow made a runtime dependency. Owner reviews a sheet of rendered combos before step 2.
2. Registry + config: `smithing.toml`, models (parts, traits, quality, accessory), loader validation, tests for the config shape.
3. `services/smithing.py` + part instances + migration 0011 (columns); unit tests: power sum, 3-trait cap, quality roll, area tier cap,
   salvage keeps only the picked trait and refuses own tools, part swap gate.
4. `effective_stats` from parts/traits/quality/enchant; one-enchant rule; engines' tests still pass.
5. Part drops in all four skills (shared helper) + Smithing xp/level.
6. UI: Tools page tabs (Smithing, Parts, Salvage), Upgrade tab removed, tool view; hub layout test.
7. Refund + reset migration, remove upgrade/fork chains and `services/upgrades.py`, retire stat-enchant scrolls (`remove-item` skill).
8. Accessories (2 slots per skill, per-skill trait pools, shop basics + drops) and the Light skills tab.
9. Art: the full cosmetic set (palettes, frames, overlays) + accessory icons (`make-emoji`, owner approves).
10. DESIGN.md section "Tools and Smithing", STATUS update, delete this plan.

## Not in this plan
Player shop (listings, prices, fees); second ability slot; combat/sword tools (paused).

## Verification
- `python -m scripts.quick_tests` + ruff after each step; `scripts.balance` before/after steps 4-5 (tool power must keep each skill's pay
  in the guard range of `tests/test_economy_guard.py`; tune `smithing.toml`, not tests).
- Migration test on a copy of the DB: a player with an upgraded forked pickaxe + enchants gets the right refund, 4 starters, no instances left.
- Hub test: Tools page tabs render within Discord limits; smith a tool end to end with fake interactions (`tests/test_hub.py` helpers).
