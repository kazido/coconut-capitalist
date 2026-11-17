# Brief 001: remove the stale "max" line on the community tree page

Plan: none (a first, small trial brief for the local executor) · Executor: read `docs/EXECUTOR.md` first.

## Goal
The community tree page used to say "✅ max: you are paid for 50% of the tree" when a lone chopper hit the old pay cap. The cap is now 100%
(`[community] max_share = 1.0` in `configs/foraging.toml`) and pay comes from a growing pool instead, so that line is wrong whenever it shows.
Remove it. The page should only say whether you qualify for drops.

## Files you may touch
- `cococap/screens/forage.py`: the community tree page `build` (look for `max_share`, about line 423).
- `tests/test_hub.py`: one new test next to `test_two_players_chop_the_community_tree_together` (about line 1348).

## Reuse, do not reinvent
- The helpers and fixtures used by `test_two_players_chop_the_community_tree_together` (`OPEN_HOUR`, `hub`, `click`, `foraging_service`,
  `monkeypatch` time) to open the community page.

## Behaviour (be exact)
1. Delete the `if view.share >= rules.community.max_share:` block (two lines) that overrides `status`.
2. `status` stays: "✅ you qualify for drops" once `view.share >= need`, otherwise the "keep going: ... qualifies you for drops" text.
3. Do not change `max_share` itself or any service code: it is still used by `community_shares` in `cococap/services/foraging.py`.

## Tests that prove it
- `test_the_community_page_never_claims_a_max_pay_line`: open the community tree page as a player who has done ALL the damage (share 1.0)
  and assert the page text does not contain the word `max:` and does contain `you qualify for drops`.

## Done means
- `scripts/verify.sh` prints `VERIFY PASSED`.
- One commit. Message: `Community tree page: drop the stale "max" pay line (the cap is 100% now; pay comes from the pool)`.

## Do not
- Do not run the full test suite or touch any file outside the two above.

## Attempt log (the planner fills this in after each round)
