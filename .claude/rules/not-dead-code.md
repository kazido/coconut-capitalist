---
paths:
  - "cococap/exts/**"
  - "cococap/services/combat.py"
  - "cococap/screens/fight.py"
  - "cococap/screens/party.py"
  - "utils/**"
  - "scripts/import_mongo.py"
---

# Deliberately still here (not dead code; do not delete)

- `exts/core/party_system.py`: the live /party command group and right-click invite/kick; `screens/party.py` is the hub page for the same service.
- `exts/gambling/king_of_the_hill.py`: a guild-specific feature with hard-coded ids (TODO: generalize).
- `exts/utils/extensions.py` + `utils/pagination.py`: owner tooling for loading/unloading extensions.
- `services/combat.py`, `screens/fight.py`, combat tests: combat is paused, not removed.
- `scripts/import_mongo.py`: the one-time old-player migration, waiting on a working Mongo login.
- `exts/economy/drops.py`: old channel-drop code (Mongo era), to be rebuilt on the drop tables.
