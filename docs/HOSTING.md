# Hosting and going live (notes, not built yet)

Goal: the bot and its database run 24/7, while you and Claude keep developing and pushing updates without touching the live
database or needing your PC on.

## The shape

| | **Live** | **Dev** |
|---|---|---|
| Discord application | the real bot (its own token) | a second "test" bot (its own token) |
| Database | `data/cococap.db` on the server | `data/dev.db` on your PC |
| Runs where | a small always-on server (VPS) | your PC, when you are working |
| Code | the `master` branch | any branch |

`DATABASE_PATH` and `BOT_TOKEN` already come from the environment (`.env`), so dev and live are the same code with different
`.env` files. **Never put a token or a password in the repository, in a doc, or in a commit.**

## The server

A small VPS is enough (one core, 1 GB RAM): Hetzner, DigitalOcean or Oracle's free tier, around $4-6 a month. Alternatives: a
Raspberry Pi at home (free after buying it, but it depends on your internet), or Fly.io / Railway with a persistent volume.
SQLite wants one process on a real disk, so avoid hosts with throwaway disks.

- Run the bot under **systemd** (or Docker): restarts it if it crashes, and starts it at boot.
- Only one copy of the bot may use a token at a time. Never run the live token on your PC.

## Backups (do this before anything else)

- A nightly `sqlite3 data/cococap.db ".backup 'backups/cococap-YYYYMMDD.db'"` (a safe copy while the bot runs), kept for 14 days.
- Copy the newest backup off the server (a cloud bucket, or `rclone` to Drive).
- Take one more right before every deploy.

## Deploying an update

1. Work on a branch with the dev bot and `data/dev.db`; tests and lint must pass.
2. Open a PR into `master` and merge it.
3. A GitHub Action (on push to `master`) connects to the server over SSH and runs: backup, `git pull`, install requirements if they
   changed, restart the service. Migrations (`alembic`) already run when the bot starts.
4. Roll back: `git checkout <previous commit>`, restore the pre-deploy backup if a migration ran, restart.

Pushing is always your call: nothing here is automatic until you ask for it.

## Going live with the current database

1. Everyone stops playing; copy `data/cococap.db` (and `-wal`, `-shm`, or take a `.backup`) to the server.
2. Point the live `.env` at it and start the bot. Keep the dev bot on a *copy* (`data/dev.db`).
3. The tokens/ranks migration from the old MongoDB (below) runs once, on the live copy, after a backup.

## Migrating the old players (ranks and tokens only)

`scripts/import_mongo.py` knows the old document format. The plan: read the old users **read-only**, then for each player copy only
their `rank` and `tokens` into the live database (creating them if needed), leave bits and everything else fresh, and give anyone
who had pets one basic pet. It prints every change and needs a fresh backup first. The MongoDB address and password are passed on
the command line or in the environment for that one run, and are never written to a file.
