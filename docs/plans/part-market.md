# Part market: travelling merchant + black market
Status: approved idea (owner, 2026-11-19); numbers are first guesses.

Two Shop tabs that sell smithing parts for bits. Mid-game convenience, late-game money sink for players chasing perfect parts.

- **Travelling Merchant** (tab "Merchant"): unlocks once the player has reached **Rust Belt** (area 3). New stock **every hour**.
  3 parts, mostly tier 1-3 (sometimes a tier 4), normal fresh traits. Cheap enough to fill a missing slot.
- **Black Market** (tab "Black Market"): unlocks at **Star Kingdom** (area 6). New stock **once a day**. 4 parts, tier 4-7, each rolling
  the most traits for its tier (+1, capped at the pool). Steep prices that climb with tier: the money sink.
- Stock is **per player** and needs no table: it is rolled from `random.Random(f"{user_id}:{shop}:{window}")`, where window = the hour (or
  day) number, so it is the same every time you look in that window. Bought slots are remembered with a stat `market_<shop>_<window>_<slot>`.
- Price = `tier_price[tier] * (1 + trait_premium * traits)`. All numbers in `configs/market.toml` (unlock area, refresh seconds, slots,
  tier weights, prices), TODO(balance).
- Rules in `services/market.py` (no discord): `stock(user, shop, now)`, `buy(user, shop, slot, now)`; buying gives a part instance
  exactly as rolled (same tier and traits), charges bits, refuses if locked, already bought, or too poor (GameRuleError).
- UI: two panes on `ShopScreen` (`screens/shop.py`); show "restocks in 34m" and each part's tier, type, traits and price; one dropdown + Buy.
- Tests: same stock within a window, new stock next window, locked before the area, can't buy a slot twice, the bought part matches.
