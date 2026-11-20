---
paths:
  - "cococap/db/**"
  - "migrations/**"
  - "tests/test_db_migrations.py"
---

# Database changes

- **A DB change**: new Alembic migration in `migrations/versions/` (and update `cococap/db/tables.py`); `tests/test_db_migrations.py`
  checks the schema matches.
- Back up `data/cococap.db` (copy into `data/backups/`) before anything that touches it. It is the live-ish database.
- Tests use the real SQLite fixture `db` (`tests/conftest.py`); never mock the DB.
