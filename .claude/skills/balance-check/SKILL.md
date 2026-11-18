---
name: balance-check
description: Check or tune Coconut Capitalist balance (what a skill pays, tool/upgrade steps, drop odds, capstones, shipments). Runs the balance report and the guard tests and reports numbers. Use before and after changing any number in configs/.
---

# Balance check

1. Know the targets: `docs/DESIGN.md` ("Where the bits come from", the phase section for the system).
2. Baseline: `.venv/bin/python -m scripts.balance` (bits per active minute per skill at starter gear). Save the output in the scratchpad.
3. For one system, write a small Monte-Carlo sim in the scratchpad that imports the real services/registry (fixed seeds, thousands of runs)
   instead of estimating by hand. Compare options in the same units (bits or xp per active minute, or a % over the baseline).
4. Change the TOML only (never a hard-coded number in code). Re-run the report; compare to baseline.
5. Run the guards that cover it: `tests/test_economy_guard.py` (income spread, drop top-heaviness), `tests/test_mastery.py` (capstones within
   ~15% of each other), `tests/test_shipments.py` (shipments pay more than selling), `tests/test_upgrades.py`.
6. Report a table: before, after, target, and what is estimated vs simulated. Record decided numbers in DESIGN.md.
