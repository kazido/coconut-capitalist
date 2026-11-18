# Skill stat trackers (plan, NOT built; waiting for the user's answer)

How stats work today: `Stats` page (Player > Stats tab, `screens/stats.py` + `services/stats.py`) is ONE dropdown of pages: General, Gambling, Minigames, Skills (a levels list). Counters are rows
in the `stats` table (`StatRow`: user, name, int value) written with `user.inc_stat(name, n)` / `set_stat` (a "best" stat = read, compare, set). Per-skill documents also keep a few counters
(`Mining.stats.lodes_mined`, `Fishing.stats.fish_caught/bosses_beaten/caught{}`, `Foraging.stats.trees_chopped/chops`, `Farming.stats.crops_grown`). A new stat name just starts at 0: **no migration**.
Layout: keep it a tab, no new top-level screens. Replace the one "Skills" levels page with one page PER SKILL in the existing dropdown (Mining, Fishing, Foraging, Farming, Pets, Shipments, Casino beside the current General/Gambling/Minigames), each with grouped lines. Each skill screen gets nothing new; its Mastery-style "Stats" link can open `player` tab=stats page=<skill>.
Existing players: every new counter starts at 0 from the day it ships, and each new page says so in one line ("Tracked since <update>"). Cheap backfills only where data already exists: fish caught by species (`caught{}`), bosses, quests, crops_grown, trees_chopped, lodes_mined, reactor level, pets owned, shipments (none stored: 0).

Proposed stats (hook = where it is recorded; all one-line `inc_stat`/best-of):
- **Mining** (settle_run / dig): deepest row reached (best), mines entered, safe exits, collapses survived (Lifeline) and collapses, vault floors reached, biggest haul in bits (best), ores by type (copper/iron/gold...: one counter per ore id), vents dug, braces used, bombs used, wyrmholes found, implosion gems, magnet rows aimed.
- **Fishing** (cast/catch): biggest fish (cm, best), fish by rarity (7 counters), longest streak without a snap, bosses beaten (have), treasures (have), quests done (have), crab pot hauls, radar scans.
- **Foraging** (chop/fell): trees felled (have), best chop streak, rarest drop found (rate, best), species felled (per species), Bloom donations (have), wedges used, grove/party tree hits.
- **Farming** (harvest/tend/water): crops harvested by crop (per seed id), tends done, cycles tended, plots watered, most plots ready at once, deeds bought, market sales (bits sold), anomalies, rain-god blessings (have).
- **Pets**: pets owned, orbs opened, highest pet level, pet foods fed. **Shipments**: crates shipped by skill, total bits paid. **Casino**: already tracked (add biggest bet, total bits won/lost net).
Cost: about 40 `inc_stat` calls in the services plus one `stat_pages` entry per skill; tests assert each hook increments once (a guard that every proposed stat name is written somewhere in services, by grep over the list).

Question: build all of it (the per-skill pages in the Stats dropdown, about 40 counters), or start with Mining + Fishing + Foraging + Farming only and add Pets/Shipments/Casino later?
