"""The bot's custom emojis, looked up **by name**.

The emojis are *application emojis* (uploaded in the Developer Portal, owned by the bot, usable in any
server). At startup ``refresh(bot)`` fetches them, so data files and code only need to say
``ore_iron`` -- never a numeric id that could be mistyped or go stale.

* ``get("cell", "⬛")``  -> the emoji's mention string, or the fallback if it isn't uploaded.
* ``resolve("<a:gemstone_rage:123>")`` -> the same emoji looked up by name (so a wrong/old id in a data
  file still works); text without custom emojis is returned unchanged.

Before ``refresh`` runs (tests, offline tools) nothing is known and every lookup falls back.
"""

import re
from logging import getLogger

log = getLogger(__name__)

# The bot's uploaded emojis. Startup warns about any of these that are missing, and a test fails if one
# stops being used anywhere (so no artwork silently goes to waste).
KNOWN = (
    "autominer", "cell", "cell_empty", "cell_upgraded", "wyrmhole", "seed_weathered",
    "gemstone_balance", "gemstone_implosion", "gemstone_oreo", "gemstone_peace", "gemstone_rage", "gemstone_sanity",
    "ore_copper", "ore_gold", "ore_iron",
    "spirit_of_the_forest", "spirit_of_the_mines", "spirit_of_the_sea",
    "xp_bar_empty", "xp_bar_full", "xp_bar_left", "xp_bar_right",
)

_TOKEN = re.compile(r"<a?:(\w+):\d+>")
_by_name: dict[str, str] = {}


def load(emojis) -> None:
    """Replace the known emojis with `emojis` (anything with ``.name`` and a mention ``str()``)."""
    _by_name.clear()
    _by_name.update({e.name: str(e) for e in emojis})


async def refresh(bot) -> None:
    """Fetch the bot's application emojis. A failure only means fallbacks are used."""
    try:
        load(await bot.fetch_application_emojis())
    except Exception:  # network / permissions: the bot still works with plain emoji
        log.exception("Could not fetch application emojis; using fallbacks")
        return
    log.info("Loaded %d application emojis: %s", len(_by_name), ", ".join(sorted(_by_name)))
    if missing := [n for n in KNOWN if n not in _by_name]:
        log.warning("Application emojis the bot expects but could not find: %s", ", ".join(missing))
    if extra := sorted(set(_by_name) - set(KNOWN)):
        log.info("Application emojis the bot does not use yet: %s", ", ".join(extra))


def get(name: str, fallback: str = "") -> str:
    return _by_name.get(name, fallback)


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
