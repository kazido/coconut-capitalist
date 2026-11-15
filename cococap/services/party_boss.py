"""Party boss fights: a fishing boss one party member hooks can be joined by the rest of the party.

When a member of a party of two or more hooks a boss, a fight opens for the party and stays open for `fight_seconds`. Anyone in the party can join it from their
Fishing page. Everyone reels **their own set of arrows** (the same boss and the same twists, a different reel for each person, with their own rod's slack), so it is
a team effort and not one person's clicks. Everyone who lands their reel is paid: the boss's rewards, and **more for every extra member who landed theirs** (+25% each,
up to doubling). Someone who slips off the hook only loses their own share. The fight is settled once, in one transaction, and each member collects their payout from
their own Fishing page, like a party tree.
"""

import random
import time
from collections import Counter
from dataclasses import dataclass, field

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.services import community, fishing
from cococap.services.party import Party, xp_multiplier
from cococap.user import User

KEEP = {"current": None, "pending": {}, "count": 0}


class PartyBossError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


def _key(party_id: int) -> str:
    return f"party_boss:{party_id}"


@dataclass(frozen=True)
class FightView:
    number: int
    boss: str
    modifiers: tuple[str, ...]
    status: str  # open | won | lost
    closes_at: float
    reeling: int
    done: int
    failed: int
    you: str | None  # "reeling" | "done" | "failed" | None (not in it)

    @property
    def is_open(self) -> bool:
        return self.status == "open"


@dataclass(frozen=True)
class Payout:
    boss: str
    bits: int
    xp: int
    items: Counter = field(default_factory=Counter)
    teammates: int = 0  # how many OTHER members landed theirs
    bonus: float = 0.0  # the team bonus that was applied
    slack_bits: int = 0


def team_bonus(finishers: int, rules) -> float:
    """+bonus_per_extra for every extra member who landed their reel, up to max_bonus."""
    return min(rules.fishing.boss.party.max_bonus, rules.fishing.boss.party.bonus_per_extra * max(0, finishers - 1))


def _settle(state: dict, party_id: int, reg: Registry) -> None:
    """Work out everyone's payout for the fight that just ended, exactly once. Anyone still reeling when it ends has run out of time."""
    fight = state["current"]
    if fight is None or fight["settled"]:
        return
    fight["settled"] = True
    for entry in fight["players"].values():
        if entry["state"] == "reeling":
            entry["state"] = "failed"
    done = {uid: e for uid, e in fight["players"].items() if e["state"] == "done"}
    fight["status"] = "won" if done else "lost"
    if not done:
        return
    bonus = 1 + team_bonus(len(done), reg)
    boss = reg.fishing.boss
    for uid, entry in done.items():
        rng = random.Random(f"party-boss:{party_id}:{fight['number']}:{uid}")
        bits, items = fishing.roll_boss_reward(reg, rng)
        bits = round(bits * bonus)
        slack_bits = fishing.slack_bonus(bits, entry.get("slack", 0), reg.fishing)
        state["pending"].setdefault(uid, []).append({
            "boss": fight["boss"], "bits": bits + slack_bits, "slack_bits": slack_bits, "xp": round(boss.xp * bonus),
            "items": {i: round(q * bonus) for i, q in items.items()}, "teammates": len(done) - 1, "bonus": bonus - 1})


def _expire(state: dict, party_id: int, now: float, reg: Registry) -> None:
    fight = state["current"]
    if fight is not None and not fight["settled"] and now >= fight["closes"]:
        _settle(state, party_id, reg)


def _view(state: dict, user_id: int) -> FightView | None:
    fight = state["current"]
    if fight is None:
        return None
    states = [e["state"] for e in fight["players"].values()]
    mine = fight["players"].get(str(user_id))
    return FightView(fight["number"], fight["boss"], tuple(fight["modifiers"]), fight["status"], fight["closes"], states.count("reeling"),
                     states.count("done"), states.count("failed"), mine["state"] if mine else None)


async def _party(user: User) -> Party | None:
    party = await Party.for_user(user.id)
    return party if party is not None and party.member_count() >= 2 else None


async def open_fight(user: User, boss: str, modifiers: list[str], now: float | None = None, registry: Registry | None = None) -> FightView | None:
    """You hooked a boss: open a party fight for your party (None if you have no party of two or more, or a fight is already open)."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    party = await _party(user)
    if party is None:
        return None

    def start(state: dict) -> FightView | None:
        _expire(state, party.party_id, now, reg)
        current = state["current"]
        if current is not None and not current["settled"]:
            return None  # one fight at a time: this boss is yours alone
        state["count"] += 1
        state["current"] = {"number": state["count"], "boss": boss, "modifiers": list(modifiers), "opened": now,
                            "closes": now + reg.fishing.boss.party.fight_seconds, "status": "open", "settled": False,
                            "players": {str(user.id): {"state": "reeling", "slack": 0}}}
        return _view(state, user.id)

    return await community.update(_key(party.party_id), KEEP, start)


async def view(user: User, now: float | None = None, registry: Registry | None = None) -> FightView | None:
    """Your party's current fight (a finished one stays visible until the next opens). None without a party or a fight."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    party = await Party.for_user(user.id)
    if party is None:
        return None

    def look(state: dict) -> FightView | None:
        _expire(state, party.party_id, now, reg)
        return _view(state, user.id)

    return await community.update(_key(party.party_id), KEEP, look)


async def join(user: User, now: float | None = None, registry: Registry | None = None) -> FightView:
    """Join your party's open fight: you get your own reel."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    party = await _party(user)
    if party is None:
        raise PartyBossError("You need a party to join a boss fight.")

    def enter(state: dict) -> FightView:
        _expire(state, party.party_id, now, reg)
        fight = state["current"]
        if fight is None or fight["settled"]:
            raise PartyBossError("Your party has no boss fight open.")
        if str(user.id) in fight["players"]:
            raise PartyBossError("You are already in this fight.")
        fight["players"][str(user.id)] = {"state": "reeling", "slack": 0}
        return _view(state, user.id)

    return await community.update(_key(party.party_id), KEEP, enter)


async def report(user: User, outcome: str, slack: int = 0, now: float | None = None, registry: Registry | None = None) -> FightView | None:
    """Your reel is over: "done" (you landed it, with `slack` to spare) or "failed" (it slipped off). Settles the fight once everyone is finished."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    party = await Party.for_user(user.id)
    if party is None:
        return None

    def finish(state: dict) -> FightView | None:
        _expire(state, party.party_id, now, reg)
        fight = state["current"]
        mine = fight["players"].get(str(user.id)) if fight else None
        if fight is None or mine is None or fight["settled"] or mine["state"] != "reeling":
            return _view(state, user.id)  # (the fight ended while you were reeling: you ran out of time)
        mine["state"], mine["slack"] = outcome, slack
        if all(e["state"] != "reeling" for e in fight["players"].values()):
            _settle(state, party.party_id, reg)
        return _view(state, user.id)

    return await community.update(_key(party.party_id), KEEP, finish)


async def claim(user: User, now: float | None = None, registry: Registry | None = None) -> list[Payout]:
    """Collect what you are owed from finished fights (once each)."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    party = await Party.for_user(user.id)
    if party is None:
        return []

    def take(state: dict) -> list[dict]:
        _expire(state, party.party_id, now, reg)
        return state["pending"].pop(str(user.id), [])

    owed = await community.update(_key(party.party_id), KEEP, take)
    paid = []
    mult = await xp_multiplier(user.id, reg, "fishing")
    for entry in owed:
        xp = round(entry["xp"] * mult)
        for item_id, quantity in entry["items"].items():
            await user.add_item(item_id, quantity)
        if entry["bits"]:
            await user.add_bits(entry["bits"])

        def win(skill, name=entry["boss"], xp=xp) -> None:
            skill.xp += xp
            skill.stats.bosses_beaten += 1
            skill.stats.bosses[name] = skill.stats.bosses.get(name, 0) + 1

        await user.update_skill("fishing", win)
        paid.append(Payout(entry["boss"], entry["bits"], xp, Counter(entry["items"]), entry["teammates"], entry["bonus"], entry["slack_bits"]))
    return paid
