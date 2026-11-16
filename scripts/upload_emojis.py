"""Upload the files in ``art/out/`` to the bot as *application emoji* (run this on your own machine).

    .venv/bin/python scripts/upload_emojis.py                  # dry run (default): prints the plan, touches nothing
    .venv/bin/python scripts/upload_emojis.py --yes            # really upload what is missing
    .venv/bin/python scripts/upload_emojis.py --only ui_ --yes # only names starting with a prefix
    .venv/bin/python scripts/upload_emojis.py --replace iron_ore --yes   # delete + recreate one emoji (new art)
    .venv/bin/python scripts/upload_emojis.py --limit 50 --yes # at most 50 uploads this run (rerun for the rest)

A file ``art/out/<name>.png`` (static) or ``.webp`` / ``.gif`` (animated) becomes the emoji ``<name>``. Only names
the bot does not have yet are uploaded, so the script is safe to rerun and resumes after an interruption. The bot
token comes from ``.env`` / the environment exactly like the bot's own (it is never printed). Restart the bot after
uploading: it fetches its emoji at startup. Naming rules: see ``cococap/emojis.py`` and docs/DESIGN.md.

The planning (`plan_upload`) is pure, so it is unit-tested without Discord or a token.
"""

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "art" / "out"

NAME_RE = re.compile(r"^[a-z0-9_]{2,32}$")  # Discord's rule for application emoji names
EXTENSIONS = (".png", ".webp", ".gif", ".jpg", ".jpeg")
MAX_BYTES = 256 * 1024  # Discord's limit per emoji image
MAX_SLOTS = 2000  # application emoji slots


@dataclass(frozen=True)
class EmojiFile:
    name: str
    path: Path
    size: int

    @classmethod
    def from_path(cls, path: Path) -> "EmojiFile":
        return cls(path.stem, path, path.stat().st_size)


@dataclass
class Plan:
    upload: list[EmojiFile] = field(default_factory=list)  # new names to create
    replace: list[EmojiFile] = field(default_factory=list)  # existing names to delete and recreate
    skipped: list[str] = field(default_factory=list)  # already on Discord (or filtered out by --only)
    invalid: list[tuple[str, str]] = field(default_factory=list)  # (name, reason): will not be uploaded
    deferred: list[str] = field(default_factory=list)  # valid, but over --limit or out of slots this run
    slots_used: int = 0  # how many slots are in use after the plan runs (if everything succeeds)

    @property
    def actions(self) -> list[tuple[str, EmojiFile]]:
        return [("replace", f) for f in self.replace] + [("upload", f) for f in self.upload]


def check_file(f: EmojiFile) -> str | None:
    """Why this file can't be uploaded, or None."""
    if not NAME_RE.match(f.name):
        return "name must be 2-32 characters of a-z, 0-9 and _"
    if f.size > MAX_BYTES:
        return f"{f.size / 1024:.0f} KB is over the {MAX_BYTES // 1024} KB limit"
    if f.size == 0:
        return "empty file"
    return None


def plan_upload(
    existing_names,
    files,
    *,
    only: str | None = None,
    replace=(),
    limit: int | None = None,
    max_slots: int = MAX_SLOTS,
) -> Plan:
    """Decide what to do. `existing_names`: names already on Discord; `files`: `EmojiFile`s from art/out.

    Missing names are uploaded; names in `replace` are deleted and recreated (only if a file exists);
    `only` keeps names with that prefix; `limit` caps the number of uploads+replacements this run.
    """
    existing, replace = set(existing_names), set(replace)
    plan = Plan(slots_used=len(existing))
    by_name: dict[str, list[EmojiFile]] = {}
    for f in files:
        by_name.setdefault(f.name, []).append(f)

    todo: list[tuple[str, EmojiFile]] = []
    for name in sorted(by_name):
        if only and not name.startswith(only):
            plan.skipped.append(name)
            continue
        if len(by_name[name]) > 1:
            plan.invalid.append((name, "more than one file with this name (" + ", ".join(sorted(x.path.suffix for x in by_name[name])) + ")"))
            continue
        f = by_name[name][0]
        if problem := check_file(f):
            plan.invalid.append((name, problem))
        elif name in existing and name not in replace:
            plan.skipped.append(name)
        else:
            todo.append(("replace" if name in existing else "upload", f))
    for name in sorted(replace - set(by_name)):
        plan.invalid.append((name, "--replace: no file with this name in the art folder"))

    budget = len(todo) if limit is None else max(limit, 0)
    for kind, f in todo:
        grows = kind == "upload"
        if budget <= 0 or (grows and plan.slots_used >= max_slots):
            plan.deferred.append(f.name)
            continue
        budget -= 1
        (plan.upload if grows else plan.replace).append(f)
        plan.slots_used += grows
    return plan


def find_files(folder: Path = OUT_DIR) -> list[EmojiFile]:
    if not folder.is_dir():
        return []
    return [EmojiFile.from_path(p) for p in sorted(folder.iterdir()) if p.is_file() and p.suffix.lower() in EXTENSIONS]


def print_plan(plan: Plan, existing_count: int) -> None:
    for kind, f in plan.actions:
        print(f"  {kind:<8} {f.name}  ({f.size / 1024:.1f} KB)")
    for name, why in plan.invalid:
        print(f"  INVALID  {name}: {why}")
    if plan.deferred:
        print(f"  later    {len(plan.deferred)} more (over --limit or out of slots): {', '.join(plan.deferred[:8])}{' ...' if len(plan.deferred) > 8 else ''}")
    print(
        f"Plan: {len(plan.upload)} to upload, {len(plan.replace)} to replace, {len(plan.skipped)} already there / filtered, "
        f"{len(plan.invalid)} invalid, {len(plan.deferred)} deferred. Slots: {existing_count} used now, {plan.slots_used} of {MAX_SLOTS} after."
    )


async def _with_backoff(make_call, label: str, tries: int = 6):
    """Run an API call, waiting out rate limits (HTTP 429) with growing pauses."""
    import discord

    delay = 5.0
    for attempt in range(1, tries + 1):
        try:
            return await make_call()
        except discord.HTTPException as e:
            if e.status != 429 or attempt == tries:
                raise
            wait = float(getattr(e, "retry_after", None) or delay)
            print(f"    rate limited on {label}; waiting {wait:.0f}s (try {attempt}/{tries})")
            await asyncio.sleep(wait)
            delay = min(delay * 2, 120)


async def run(args: argparse.Namespace, token: str) -> int:
    import discord

    client = discord.Client(intents=discord.Intents.none())
    uploaded, replaced, failed = [], [], []
    code = 0

    async with client:
        await client.login(token)
        existing = await client.fetch_application_emojis()
        by_name = {e.name: e for e in existing}
        plan = plan_upload(by_name, find_files(), only=args.only, replace=args.replace or (), limit=args.limit)
        print_plan(plan, len(existing))
        if not args.yes:
            print("Dry run: nothing was changed. Add --yes to upload.")
            return 1 if plan.invalid else 0
        for kind, f in plan.actions:
            try:
                if kind == "replace":
                    await _with_backoff(by_name[f.name].delete, f"delete {f.name}")
                await _with_backoff(
                    lambda f=f: client.create_application_emoji(name=f.name, image=f.path.read_bytes()), f"upload {f.name}"
                )
                (replaced if kind == "replace" else uploaded).append(f.name)
                print(f"  ok       {f.name}")
            except Exception as e:  # keep going; rerun to retry the failures
                failed.append((f.name, str(e)[:120]))
                print(f"  FAILED   {f.name}: {e}")
            await asyncio.sleep(args.pause)
        used = len(await client.fetch_application_emojis())

    print(f"\nUploaded {len(uploaded)}, replaced {len(replaced)}, skipped {len(plan.skipped)}, failed {len(failed)}, invalid {len(plan.invalid)}, deferred {len(plan.deferred)}.")
    print(f"Slots used: {used} of {MAX_SLOTS}.")
    for name, why in failed:
        print(f"  failed: {name}: {why}")
    if uploaded or replaced:
        print("Restart the bot so it loads the new emoji.")
    if failed:
        code = 1
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Upload art/out/ files to the bot as application emoji (dry run unless --yes).")
    ap.add_argument("--yes", action="store_true", help="really upload (default is a dry run that only prints the plan)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan only (this is the default)")
    ap.add_argument("--only", metavar="PREFIX", help="only names starting with PREFIX")
    ap.add_argument("--replace", metavar="NAME", action="append", help="delete and recreate this emoji (repeatable)")
    ap.add_argument("--limit", type=int, metavar="N", help="at most N uploads/replacements this run")
    ap.add_argument("--pause", type=float, default=1.5, help="seconds to wait between uploads (default 1.5)")
    args = ap.parse_args(argv)
    if args.dry_run:
        args.yes = False

    sys.path.insert(0, str(ROOT))
    from cococap import constants  # loads .env the same way the bot does

    if not constants.TOKEN:
        print("No BOT_TOKEN found in .env or the environment (see .env.example). Nothing to do.")
        return 2
    if not OUT_DIR.is_dir():
        print(f"{OUT_DIR} does not exist yet: nothing to upload.")
        return 2
    try:
        return asyncio.run(run(args, constants.TOKEN))
    except Exception as e:  # login failure etc.: never echo anything that could hold the token
        print(f"Could not talk to Discord: {type(e).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
