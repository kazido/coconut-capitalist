"""Party trees: a tree only your party can chop, with a little better rewards for working as a team.

Any member of a party of two or more starts one (in a forest everybody in the party has unlocked) and it stands for a while.
Every chop is applied inside one serialized transaction (``services.community``), so any number of members can chop at the
same moment without losing a chop, and the tree can only fall once. When it falls (or falls over), everyone's reward is
worked out once, in that same transaction, and kept until each member collects it from their own panel.
"""

import random
import time
from collections import Counter
from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.registry.models import ForagingRules
from cococap.services import community, foraging, releaf
from cococap.services.party import Party, xp_multiplier
from cococap.user import User

KEEP = {"current": None, "pending": {}}


class PartyTreeError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


def _key(party_id: int) -> str:
    return f"party_tree:{party_id}"


def party_rules(rules: ForagingRules) -> ForagingRules:
    """The foraging rules with the community tree's reward settings swapped for the party tree's, so the same (tested) share
    calculation pays out a party tree."""
    p = rules.party_tree
    return rules.model_copy(update={"community": rules.community.model_copy(update={
        "min_share": p.min_share, "group_bonus": p.group_bonus, "max_group_bonus": p.max_group_bonus,
        "expired_factor": p.expired_factor, "max_share": 1.0, "pool_base": 1.0, "pool_per_chopper": 0.0})})  # (the pool that grows with the crowd is for the community tree; a party tree pays all of itself)


def tree_hp(zone: int, members: int, rules: ForagingRules) -> int:
    return max(1, round(foraging.average_hp(zone, rules) * rules.party_tree.hp_per_member * members))


@dataclass(frozen=True)
class PartyTreeView:
    number: int
    zone: int
    max_hp: int
    hp: int
    status: str  # growing | felled | expired
    closes_at: float
    chops: dict[int, int]  # member id -> hp chopped
    yours: int
    species: str = ""  # the tree's species id (rolled when it was started)

    @property
    def standing(self) -> bool:
        return self.status == "growing"

    @property
    def fraction_left(self) -> float:
        return self.hp / self.max_hp if self.max_hp else 0.0

    @property
    def share(self) -> float:
        return self.yours / self.max_hp if self.max_hp else 0.0


def _settle(state: dict, party_id: int, rules: ForagingRules, reg: Registry) -> None:
    """Work out everyone's reward for the tree that just ended (felled or fallen over), exactly once."""
    tree = state["current"]
    if tree is None or tree["settled"]:
        return
    tree["settled"] = True
    rng = random.Random(f"party-tree:{party_id}:{tree['number']}")
    chops = {int(u): d for u, d in tree["chops"].items()}
    if not chops:
        return
    efforts = {int(u): e for u, e in tree.get("efforts", {}).items()}
    shares = foraging.community_shares(tree["max_hp"], tree["status"] == "felled", chops, party_rules(rules), rng, reg, tree["zone"],
                                       efforts=efforts, species=tree.get("species", ""), boost=tree.get("bloom", 0.0))
    for user_id, share in shares.items():
        state["pending"].setdefault(str(user_id), []).append(
            {"number": tree["number"], "drops": dict(share.drops), "bits": share.bits, "xp": share.xp, "felled": tree["status"] == "felled"})


def _expire(state: dict, party_id: int, now: float, rules: ForagingRules, reg: Registry) -> None:
    tree = state["current"]
    if tree is not None and tree["status"] == "growing" and now >= tree["closes"]:
        tree["status"] = "expired"
        _settle(state, party_id, rules, reg)


def _view(state: dict, user_id: int) -> PartyTreeView | None:
    tree = state["current"]
    if tree is None:
        return None
    chops = {int(u): d for u, d in tree["chops"].items()}
    return PartyTreeView(tree["number"], tree["zone"], tree["max_hp"], tree["hp"], tree["status"], tree["closes"], chops, chops.get(user_id, 0), tree.get("species", ""))


async def _party_of(user: User) -> Party:
    party = await Party.for_user(user.id)
    if party is None or party.member_count() < 2:
        raise PartyTreeError("Party trees need a party of two or more. Start or join one from the Party page.")
    return party


async def view(user: User, now: float | None = None, registry: Registry | None = None) -> PartyTreeView | None:
    """Your party's current tree (a finished one stays visible until the next is started). None if no party or tree."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    party = await Party.for_user(user.id)
    if party is None:
        return None

    def look(state: dict) -> PartyTreeView | None:
        _expire(state, party.party_id, now, reg.foraging, reg)
        return _view(state, user.id)

    return await community.update(_key(party.party_id), KEEP, look)


async def unlocked_zone(party: Party, registry: Registry | None = None) -> int:
    """The deepest forest that EVERY member has unlocked (so nobody is left out)."""
    reg = registry or get_registry()
    levels = [User.xp_to_level((await (await User.get(m)).skill("foraging")).xp) for m in party.members]
    return foraging.unlocked_zones(min(levels), reg.foraging)[-1]


async def start(user: User, zone: int, now: float | None = None, registry: Registry | None = None, rng: random.Random | None = None) -> PartyTreeView:
    """Start a party tree (any member can). One at a time per party."""
    reg = registry or get_registry()
    rules = reg.foraging
    now = time.time() if now is None else now
    party = await _party_of(user)
    await foraging.axe_stats(user, reg)  # (you need an axe to start a tree)
    best = await unlocked_zone(party, reg)
    if not 1 <= zone <= best:
        raise PartyTreeError(f"Your party can start trees up to forest {best} (the deepest everyone has unlocked).")
    hp = tree_hp(zone, party.member_count(), rules)
    species = foraging.roll_species(zone, rng or random.Random(), rules)

    def begin(state: dict) -> None:
        _expire(state, party.party_id, now, rules, reg)
        tree = state["current"]
        if tree is not None and tree["status"] == "growing":
            raise PartyTreeError("Your party already has a tree standing.")
        number = (tree["number"] if tree else 0) + 1
        state["current"] = {"number": number, "zone": zone, "species": species.id if species else "", "max_hp": hp, "hp": hp, "status": "growing", "opens": now,
                            "closes": now + rules.party_tree.open_minutes * 60, "chops": {}, "efforts": {}, "settled": False}

    await community.update(_key(party.party_id), KEEP, begin)
    return (await view(user, now, reg))  # type: ignore[return-value]


@dataclass(frozen=True)
class PartyChop:
    applied: int
    tree: PartyTreeView
    felled_now: bool


async def chop(user: User, damage: int, now: float | None = None, registry: Registry | None = None, effort: float = 1.0) -> PartyChop:
    """One chop on your party's tree. Atomic: all members' chops count and the tree falls once."""
    reg = registry or get_registry()
    rules = reg.foraging
    now = time.time() if now is None else now
    party = await _party_of(user)
    outcome: dict = {}
    boost = await releaf.drop_boost(reg, now)  # a Bloom up while the party chops boosts the tree's drops (kept on the tree, as it may settle later)

    def swing(state: dict) -> PartyChop:
        _expire(state, party.party_id, now, rules, reg)
        tree = state["current"]
        if tree is None or tree["status"] != "growing":
            raise PartyTreeError("Your party has no tree standing. Start one!")
        applied = min(max(1, damage), tree["hp"])
        tree["hp"] -= applied
        tree["bloom"] = max(tree.get("bloom", 0.0), boost)
        tree["chops"][str(user.id)] = tree["chops"].get(str(user.id), 0) + applied
        efforts = tree.setdefault("efforts", {})
        efforts[str(user.id)] = efforts.get(str(user.id), 0.0) + effort * applied / max(1, damage)
        if tree["hp"] == 0:
            tree["status"] = "felled"
            _settle(state, party.party_id, rules, reg)
            outcome["felled"] = True
        return PartyChop(applied, _view(state, user.id), bool(outcome.get("felled")))

    return await community.update(_key(party.party_id), KEEP, swing)


async def claim(user: User, now: float | None = None, registry: Registry | None = None) -> list[foraging.Reward]:
    """Collect everything you are owed from finished party trees (once each)."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    party = await Party.for_user(user.id)
    if party is None:
        return []

    def take(state: dict) -> list[dict]:
        _expire(state, party.party_id, now, reg.foraging, reg)
        return state["pending"].pop(str(user.id), [])

    owed = await community.update(_key(party.party_id), KEEP, take)
    rewards = []
    mult = await xp_multiplier(user.id, reg, "foraging")
    for entry in owed:
        xp = round(entry["xp"] * mult)
        await foraging._pay(user, Counter(entry["drops"]), entry["bits"], xp, trees=1 if entry["felled"] else 0)
        rewards.append(foraging.Reward(Counter(entry["drops"]), entry["bits"], xp, entry["felled"], party=True))
    return rewards
