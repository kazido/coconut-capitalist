"""Party boss fights: a fishing boss one party member hooks can be joined by the rest of the party.

When a member of a party of two or more hooks a boss, a fight opens for the party and stays open for `fight_seconds`. Anyone in the party can join it from their
Fishing page. Everyone reels **their own set of arrows** (the same boss and the same twists, a different reel for each person, with their own rod's slack), so it is
a team effort and not one person's clicks. Everyone who lands their reel is paid: the boss's rewards, and **more for every extra member who landed theirs** (+25% each,
up to doubling). Someone who slips off the hook only loses their own share. The fight is settled once, in one transaction, and each member collects their payout from
their own Fishing page, like a party tree.

The hooker can also **open the fight to everyone** (with or without a party): it is then listed on every player's Fishing page until it closes, and anyone can
join it. A fight lives under its host's key (their party, or their own id when they have none); people who join a foreign fight keep a pointer to it so their
reel reports and their payout find it.
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
PUBLIC = "party_boss_public"  # the keys of fights opened to everyone
PUBLIC_KEEP = {"keys": []}
MAX_LISTED = 20  # how many public fights one page looks at


class PartyBossError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


def _key(party_id: int) -> str:
    return f"party_boss:{party_id}"


def _solo_key(user_id: int) -> str:
    return f"party_boss:u{user_id}"


def _joined_key(user_id: int) -> str:
    return f"party_boss_joined:{user_id}"


def _seed_id(key: str) -> int:
    """The number after the colon (a party id, or a solo host's user id): only used to seed the payout dice."""
    return int(key.rpartition(":")[2].lstrip("u") or 0)


async def _home(user: User) -> str:
    """Where YOUR fights live: your party's key, or your own when you have no party."""
    party = await Party.for_user(user.id)
    return _key(party.party_id) if party is not None else _solo_key(user.id)


async def _keys(user: User) -> list[str]:
    """Every fight key you can be in: your own, then any foreign fights you joined."""
    joined = await community.read(_joined_key(user.id), {"keys": []})
    return list(dict.fromkeys([await _home(user), *joined["keys"]]))


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
    public: bool = False  # opened to everyone
    host: str = ""  # the key the fight lives under (needed to join a foreign one)
    own: bool = True  # your own fight (your party's, or yours alone), not one found on the public list

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


def _settle(state: dict, seed_id: int, reg: Registry) -> None:
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
        rng = random.Random(f"party-boss:{seed_id}:{fight['number']}:{uid}")
        bits, items = fishing.roll_boss_reward(reg, rng)
        bits = round(bits * bonus)
        slack_bits = fishing.slack_bonus(bits, entry.get("slack", 0), reg.fishing)
        state["pending"].setdefault(uid, []).append({
            "boss": fight["boss"], "bits": bits + slack_bits, "slack_bits": slack_bits, "xp": round(boss.xp * bonus),
            "items": {i: round(q * bonus) for i, q in items.items()}, "teammates": len(done) - 1, "bonus": bonus - 1})


def _expire(state: dict, seed_id: int, now: float, reg: Registry) -> None:
    fight = state["current"]
    if fight is not None and not fight["settled"] and now >= fight["closes"]:
        _settle(state, seed_id, reg)


def _view(state: dict, user_id: int, host: str = "", own: bool = True) -> FightView | None:
    fight = state["current"]
    if fight is None:
        return None
    states = [e["state"] for e in fight["players"].values()]
    mine = fight["players"].get(str(user_id))
    return FightView(fight["number"], fight["boss"], tuple(fight["modifiers"]), fight["status"], fight["closes"], states.count("reeling"),
                     states.count("done"), states.count("failed"), mine["state"] if mine else None, bool(fight.get("public")), host, own)


async def _party(user: User) -> Party | None:
    party = await Party.for_user(user.id)
    return party if party is not None and party.member_count() >= 2 else None


def _starter(user: User, boss: str, modifiers: list[str], now: float, reg: Registry, host: str, public: bool):
    """The change that opens a new fight under `host` (None if one is already open there)."""
    def start(state: dict) -> FightView | None:
        _expire(state, _seed_id(host), now, reg)
        current = state["current"]
        if current is not None and not current["settled"]:
            return None  # one fight at a time: this boss is yours alone
        state["count"] += 1
        state["current"] = {"number": state["count"], "boss": boss, "modifiers": list(modifiers), "opened": now, "host": str(user.id), "public": public,
                            "closes": now + reg.fishing.boss.party.fight_seconds, "status": "open", "settled": False,
                            "players": {str(user.id): {"state": "reeling", "slack": 0}}}
        return _view(state, user.id, host)

    return start


async def open_fight(user: User, boss: str, modifiers: list[str], now: float | None = None, registry: Registry | None = None) -> FightView | None:
    """You hooked a boss: open a party fight for your party (None if you have no party of two or more, or a fight is already open)."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    party = await _party(user)
    if party is None:
        return None
    host = _key(party.party_id)
    return await community.update(host, KEEP, _starter(user, boss, modifiers, now, reg, host, False))


async def open_to_all(user: User, boss: str, modifiers: list[str], now: float | None = None, registry: Registry | None = None) -> FightView:
    """Open the boss you hooked to everyone: it shows on every player's Fishing page until it closes. Works with or without a party."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    host = await _home(user)
    uid = str(user.id)

    def publish(state: dict) -> FightView | None:
        _expire(state, _seed_id(host), now, reg)
        current = state["current"]
        if current is not None and not current["settled"]:
            if uid not in current["players"]:
                return None  # a teammate's fight is open, not yours
            current["public"] = True  # your party fight (or an earlier open one): now everyone can see it
            return _view(state, user.id, host)
        return _starter(user, boss, modifiers, now, reg, host, True)(state)

    fight = await community.update(host, KEEP, publish)
    if fight is None:
        raise PartyBossError("Your party already has a boss fight open.")

    def add(state: dict) -> None:
        if host not in state["keys"]:
            state["keys"].append(host)

    await community.update(PUBLIC, PUBLIC_KEEP, add)
    return fight


async def _look(key: str, user: User, now: float, reg: Registry, own: bool) -> FightView | None:
    def look(state: dict) -> FightView | None:
        _expire(state, _seed_id(key), now, reg)
        return _view(state, user.id, key, own)

    return await community.update(key, KEEP, look)


async def view(user: User, now: float | None = None, registry: Registry | None = None) -> FightView | None:
    """The fight to show you: one you are in, else your party's open one, else one opened to everyone, else your last finished one."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    home = await _home(user)
    views = [v for k in await _keys(user) if (v := await _look(k, user, now, reg, k == home)) is not None]
    mine = next((v for v in views if v.is_open and v.you is not None), None) or next((v for v in views if v.is_open), None)
    if mine is not None:
        return mine
    stale = []
    for key in (await community.read(PUBLIC, PUBLIC_KEEP))["keys"][-MAX_LISTED:]:
        if key == home:
            continue
        found = await _look(key, user, now, reg, False)
        if found is None or not found.is_open or not found.public:
            stale.append(key)
        elif found.you is None:
            return found
    if stale:  # forget the ones that have closed
        await community.update(PUBLIC, PUBLIC_KEEP, lambda st: st.update(keys=[k for k in st["keys"] if k not in stale]))
    return views[0] if views else None


async def join(user: User, now: float | None = None, registry: Registry | None = None, host: str | None = None) -> FightView:
    """Join your party's open fight, or (with `host`) one opened to everyone: you get your own reel."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    home = await _home(user)
    foreign = host is not None and host != home
    if not foreign:
        if await _party(user) is None:
            raise PartyBossError("You need a party to join a boss fight.")
        host = home

    def enter(state: dict) -> FightView:
        _expire(state, _seed_id(host), now, reg)
        fight = state["current"]
        if fight is None or fight["settled"] or (foreign and not fight.get("public")):
            raise PartyBossError("That boss fight is closed." if foreign else "Your party has no boss fight open.")
        if str(user.id) in fight["players"]:
            raise PartyBossError("You are already in this fight.")
        fight["players"][str(user.id)] = {"state": "reeling", "slack": 0}
        return _view(state, user.id, host, not foreign)

    fight = await community.update(host, KEEP, enter)
    if foreign:
        def remember(state: dict) -> None:
            if host not in state["keys"]:
                state["keys"].append(host)

        await community.update(_joined_key(user.id), {"keys": []}, remember)
    return fight


async def report(user: User, outcome: str, slack: int = 0, now: float | None = None, registry: Registry | None = None) -> FightView | None:
    """Your reel is over: "done" (you landed it, with `slack` to spare) or "failed" (it slipped off). Settles the fight once everyone is finished."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    result = None
    for key in await _keys(user):
        def finish(state: dict, key=key) -> FightView | None:
            _expire(state, _seed_id(key), now, reg)
            fight = state["current"]
            mine = fight["players"].get(str(user.id)) if fight else None
            if fight is None or mine is None:
                return None
            if fight["settled"] or mine["state"] != "reeling":
                return _view(state, user.id, key)  # (the fight ended while you were reeling: you ran out of time)
            mine["state"], mine["slack"] = outcome, slack
            if all(e["state"] != "reeling" for e in fight["players"].values()):
                _settle(state, _seed_id(key), reg)
            return _view(state, user.id, key)

        found = await community.update(key, KEEP, finish)
        if result is None:
            result = found
    return result


async def claim(user: User, now: float | None = None, registry: Registry | None = None) -> list[Payout]:
    """Collect what you are owed from finished fights (once each)."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    home = await _home(user)
    owed, finished = [], []
    for key in await _keys(user):
        def take(state: dict, key=key) -> tuple[list[dict], bool]:
            _expire(state, _seed_id(key), now, reg)
            fight = state["current"]
            return state["pending"].pop(str(user.id), []), fight is None or fight["settled"]

        got, over = await community.update(key, KEEP, take)
        owed += got
        if over and key != home:
            finished.append(key)
    if finished:  # collected from those foreign fights: forget them
        await community.update(_joined_key(user.id), {"keys": []}, lambda st: st.update(keys=[k for k in st["keys"] if k not in finished]))
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
