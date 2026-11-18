"""The bot's custom emojis, looked up **by name**.

The emojis are *application emojis* (uploaded in the Developer Portal, owned by the bot, usable in any
server). At startup ``refresh(bot)`` fetches them, so data files and code only need to say
``ore_iron`` -- never a numeric id that could be mistyped or go stale.

* ``get("cell", "⬛")``  -> the emoji's mention string, or the fallback if it isn't uploaded.
* ``resolve("<a:gemstone_rage:123>")`` -> the same emoji looked up by name (so a wrong/old id in a data
  file still works); text without custom emojis is returned unchanged.

* ``for_id("item", "material_iron_ore", "⛏️")`` -> the application emoji named by the thing's id, else the fallback.
  This is how hundreds of emoji work without a single token in the data: upload ``iron_ore`` and every
  screen that shows that item switches to it. Naming convention (kind -> emoji name):

  ===========  ================  ===========================
  item         ``<item_id>``     ``iron_ore``, ``scroll_lure``
  pet          ``pet_<id>``      ``pet_ember``
  species      ``species_<id>``  ``species_birch``
  enchant      ``enchant_<id>``  ``enchant_lure``
  mine type    ``mine_<id>``     ``mine_crystal``
  water        ``water_<id>``    ``water_lake``
  rank         ``rank_<id>``     ``rank_3``
  location     ``location_<id>`` ``location_slimewood_thicket``
  area         ``area_<id>``     ``area_rust_belt``
  ship tier    ``ship_<slug>``   ``ship_dune_skiff`` (slug = the tier's name)
  ui icon      ``ui_<name>``     ``ui_releaf``
  ===========  ================  ===========================

  Custom emoji render in text, headings, button ``emoji=`` and select option emoji, but NOT in code
  blocks or button / select labels (Discord shows the raw ``<:name:id>`` there).

Before ``refresh`` runs (tests, offline tools) nothing is known and every lookup falls back.
"""

import re
from logging import getLogger

log = getLogger(__name__)

# The bot's uploaded emojis. Startup warns about any of these that are missing, and a test fails if one
# stops being used anywhere (so no artwork silently goes to waste).
LEGACY = (
    "autominer", "cell", "cell_empty", "cell_upgraded", "wyrmhole",
    "spirit_of_the_forest", "spirit_of_the_mines", "spirit_of_the_sea",
    "xp_bar_empty", "xp_bar_full", "xp_bar_left", "xp_bar_right",
)

# Every custom-emoji name the bot's own code or data may mention.
KNOWN = LEGACY

KINDS = ("item", "pet", "species", "enchant", "mine", "water", "rank", "location", "area", "ship", "ui")
NAME_RE = re.compile(r"^[a-z0-9_]{2,32}$")  # Discord's rule for application emoji names

_TOKEN = re.compile(r"<a?:(\w+):\d+>")
_by_name: dict[str, str] = {}
_meta: dict[str, tuple[int, bool]] = {}  # name -> (emoji id, animated), for big-image URLs


def load(emojis) -> None:
    """Replace the known emojis with `emojis` (anything with ``.name`` and a mention ``str()``)."""
    emojis = list(emojis)
    _by_name.clear()
    _by_name.update({e.name: str(e) for e in emojis})
    _meta.clear()
    _meta.update({e.name: (e.id, bool(getattr(e, "animated", False))) for e in emojis if getattr(e, "id", None)})


async def refresh(bot) -> None:
    """Fetch the bot's application emojis. A failure only means fallbacks are used."""
    try:
        load(await bot.fetch_application_emojis())
    except Exception:  # network / permissions: the bot still works with plain emoji
        log.exception("Could not fetch application emojis; using fallbacks")
        return
    log.info("Loaded %d application emojis: %s", len(_by_name), ", ".join(sorted(_by_name)))
    if missing := [n for n in LEGACY if n not in _by_name]:
        log.warning("Application emojis the bot expects but could not find: %s", ", ".join(missing))
    if extra := sorted(set(_by_name) - set(LEGACY)):
        log.info("Application emojis beyond the original set (found by id name): %d", len(extra))


def get(name: str, fallback: str = "") -> str:
    return _by_name.get(name, fallback)


def name_for(kind: str, id) -> str:
    """The application-emoji name for a thing: items use their bare id, everything else ``<kind>_<id>``."""
    return str(id) if kind == "item" else f"{kind}_{id}"


def for_id(kind: str, id, fallback=""):
    """The loaded application emoji named for this thing (see the table above), else `fallback`.

    `fallback` is returned untouched, so it may also be ``None`` or a ``<:name:id>`` token (resolve it
    first if it should be swapped by name).
    """
    if kind not in KINDS:
        raise ValueError(f"unknown emoji kind {kind!r}; use one of {KINDS}")
    name = name_for(kind, id)
    if name in _by_name:
        return _by_name[name]
    return fallback


def image_url(kind: str, id, size: int = 128) -> str | None:
    """The CDN picture of this thing's emoji (for big thumbnails), or None if it isn't uploaded."""
    if kind not in KINDS:
        raise ValueError(f"unknown emoji kind {kind!r}; use one of {KINDS}")
    name = name_for(kind, id)
    if name not in _meta:
        return None
    eid, animated = _meta[name]
    return f"https://cdn.discordapp.com/emojis/{eid}.{'gif' if animated else 'png'}?size={size}&quality=lossless"


def ui(name: str, fallback: str = "") -> str:
    """A UI icon: the application emoji ``ui_<name>``, else `fallback`."""
    return for_id("ui", name, fallback)


# Currency icons. Screens never hard-code these glyphs: call ``currency("bits")`` etc. so one art change is a one-file edit.
# Art: ui_bits / ui_tokens / ui_luckbucks (art/mappings/raven_magic.toml).
CURRENCY = {"bits": "💸", "tokens": "🪙", "luckbucks": "🍀"}


def bits(amount: int) -> str:
    """Bits written the way the game says them in text: "1,234 <bits icon> bits". Only for message text and headings: custom emoji
    do not render in button labels or select options/descriptions, so those keep the plain "1,234 bits"."""
    return f"{amount:,} {currency('bits')} bits"


def tokens(amount: int) -> str:
    """Tokens in message text: "3 <icon> tokens" ("1 <icon> token"). Message text only, like `bits`."""
    return f"{amount:,} {currency('tokens')} token{'' if amount == 1 else 's'}"


def luckbucks(amount: int) -> str:
    """Luckbucks in message text: "5 <icon> luckbucks" ("1 <icon> luckbuck"). Message text only, like `bits`."""
    return f"{amount:,} {currency('luckbucks')} luckbuck{'' if amount == 1 else 's'}"


def currency(name: str) -> str:
    """The icon for a currency (``bits``, ``tokens`` or ``luckbucks``): its ``ui_<name>`` emoji, else the plain glyph."""
    return ui(name, CURRENCY[name])


# Skill icons are the skill's starter tool (art already exists for them), with a plain glyph until it is uploaded.
SKILL_ICONS = {
    "mining": ("tool_pickaxe_rookie", "⛏️"),
    "fishing": ("tool_rod_starter", "🎣"),
    "foraging": ("tool_axe_starter", "🌳"),
    "farming": ("tool_can_tin", "🌽"),
    "combat": ("tool_largebranch", "⚔️"),
}


def skill(name: str, fallback: str = "") -> str:
    """The icon for a skill (mining, fishing, foraging, farming, combat): its starter tool's emoji, else the glyph."""
    item_id, glyph = SKILL_ICONS.get(name, (None, fallback))
    return for_id("item", item_id, glyph or fallback) if item_id else (glyph or fallback)


def resolve(text: str | None) -> str | None:
    """Swap every custom emoji in `text` for the same-named application emoji, if there is one."""
    if not text:
        return text
    return _TOKEN.sub(lambda m: _by_name.get(m.group(1), m.group(0)), text)


class Lazy:
    """A class attribute that looks its emoji up when read (custom emojis are only known after startup).

    ``emoji = Lazy("autominer", "⚙️")`` works both on a class and on its instances.
    """

    def __init__(self, name: str, fallback: str = ""):
        self.name, self.fallback = name, fallback

    def __get__(self, obj, owner=None) -> str:
        return get(self.name, self.fallback)
