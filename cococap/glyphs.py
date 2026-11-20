"""Every plain unicode emoji the bot writes, mapped to one of our own icons (Raven art or hand drawn: art/mappings, art/sprites/ui*.toml).

Screens and cogs keep writing ordinary glyphs ("🏆", "⬅️"). Right before a message leaves for Discord, `install()`'s hook on the HTTP
layer swaps each glyph for its custom emoji. So NO unicode emoji reaches a player once the art is uploaded, and new code is covered
without remembering to route it. A glyph whose icon is not uploaded (yet) stays as it is, so nothing breaks while art is missing.

Custom emoji do not render in button labels, select options/descriptions or placeholders. For those the leading glyph of a label moves
into the component's own ``emoji`` field, and any other glyph is dropped (so no stray plain emoji is left over).
`tests/test_glyphs.py` fails if a glyph appears in the code that has no entry here.
"""

from __future__ import annotations

import json
import re
from typing import Any

from cococap import emojis

# icon name -> glyphs. An icon is looked up with ``emojis.icon(name)``: a ``ui_<name>`` emoji, or a finished item's art (emojis.ITEM_ICONS).
# A leading "@" means a bare application emoji name (the old xp bar pieces).
_GROUPS: dict[str, str] = {
    "unknown": "❓❔🪨🌑🧵🧪🪶🔱🏜🏙🔦🪞🪡🌌🌈🧱🔘🌵🌙🗻🚰⚓🪁🌕🖤🏢💭💤🤫",
    "check": "✅✔️☑️",
    "cross": "❌✖️🚫🙅❎🗑",
    "warn": "⚠️❗❕",
    "dig": "⛏️",
    "chop": "🪓",
    "skill_fishing": "🎣🥅",
    "skill_farming": "🌽🚿",
    "tree": "🌳🌲🌴🎄🪴",
    "sprout": "🌱",
    "herb": "🌿🍃",
    "flower": "🌸🌺🌻🌷🌼🏵️🥀",
    "leaf": "🍂🍁",
    "grain": "🪵",
    "wedge": "🔩",
    "worm": "🪱",
    "battery": "🔋",
    "money": "🎰💱",
    "sell": "💰💼🛒",
    "bits": "💸",
    "tokens": "🪙",
    "luckbucks": "🍀",
    "sparkle": "✨💫🔆🌠",
    "star": "🌟⭐★",
    "book": "📖📚",
    "scroll": "📜🔢",
    "page": "📄📨📅🗓️⌨️🎫🏷️",
    "skull": "💀☠️👹👾🧟👻😞",
    "swirl": "🌀",
    "crate": "📦",
    "gift": "🎁",
    "bag": "🎒💍🧩🧿🧳🕶️",
    "people": "👤🧑🏃🧍",
    "group": "👥",
    "trade": "🤝⚖️",
    "crown": "👑",
    "record": "🏆",
    "medal": "🏅🎓",
    "medal_gold": "🥇",
    "medal_silver": "🥈",
    "medal_bronze": "🥉",
    "sword": "⚔️🗡️",
    "shield": "🛡️🔰",
    "craft": "🔨🛠️🔧🪚",
    "gear": "⚙️",
    "anvil": "🧰",
    "lock": "🔒",
    "unlock": "🔓",
    "key": "🔑",
    "search": "🔍🔎",
    "hook": "🪝",
    "crab": "🦀",
    "fish": "🐟🐠🐡🐬🐋🦈🐙🦑🦞🦐🐊🧜🪸🍣🎏",
    "paw": "🐾🐑🐈🐕🐢🐒🐨🐝🦅🐍🐉🦦🦫🐀🐇🐺🦭🦡🦔🦁🦜🦊🐸🐦🦓",
    "party": "🎉😂😍",
    "bolt": "⚡",
    "flame": "🔥⛽🏮🕯️",
    "drop": "💧🌧️",
    "wave": "🌊",
    "mist": "🌫️☁️💨",
    "world": "🌍🌐🌎🌏",
    "radar": "📡",
    "target": "🎯",
    "ruler": "📏",
    "next": "→➡️▶️▶►➤▸⏩🔜",
    "prev": "⬅️◀️◀◄⏪",
    "up": "⬆️🔼🔺",
    "down": "⬇️🔽🔻",
    "again": "🔁🔄♻️🔀↔️",
    "home": "🏠🏡",
    "box": "📥",
    "send": "🚚📤",
    "timer": "⌛⏳⏱️⏰🕐",
    "pip": "▫️▪️◾◽",
    "flag": "🏁",
    "flag_white": "🏳️",
    "cards": "🃏",
    "dice": "🎲",
    "brain": "🧠",
    "heart": "❤️💔",
    "heart_green": "💚",
    "blood": "🩸",
    "eye": "👁️",
    "gem": "💎🔷🔹",
    # Smithing trait icons (services/smithing.py TRAIT_GLYPHS): one distinct glyph each so they never swap to another icon.
    "trait_power": "💪",
    "trait_scholar": "🧾",
    "trait_appraise": "🧐",
    "trait_rare_luck": "☘️",
    "trait_drop_amount": "👝",
    "bomb": "💣",
    "boom": "💥",
    "lifeline": "🛟",
    "wyrmhole": "🕳️",
    "bug": "🪲🐌",
    "orb": "🔮",
    "sun": "🌅🌤️🌞",
    "coconut": "🥥",
    "ship": "🚢🛶⛵🛳️🚀🛸",
    "cart": "🚇",
    "basket": "🧺",
    "wheat": "🌾",
    "door": "🚪",
    "fist": "✋",
    "food": "🍽️🍔🍱🍪🥫🍯",
    "apple": "🍎🍋🍊🍇🍉🍈🫐🥔🥕🌶️🍬🫒🍄🌰🫘",
    "tips": "💡",
    "milestone": "📈📊",
    "spade": "♠",
    "suit_heart": "♥",
    "diamond": "♦",
    "club": "♣",
    "sq_black": "⬛",
    "sq_white": "⬜",
    "sq_brown": "🟫",
    "sq_green": "🟩",
    "sq_blue": "🟦",
    "sq_orange": "🟧",
    "sq_red": "🟥",
    "sq_yellow": "🟨",
    "sq_purple": "🟪",
    "dot_green": "🟢",
    "dot_red": "🔴",
    "dot_yellow": "🟡",
    "dot_orange": "🟠",
    "dot_black": "⚫",
    "dot_white": "⚪",
    "dot_brown": "🟤",
    "@xp_bar_full": "▰",
    "@xp_bar_empty": "▱",
}

# Glyphs that mean the same icon as another group's (kept out of _GROUPS so a glyph appears in just one place there).
GLYPHS: dict[str, str] = {}
for _name, _chars in _GROUPS.items():
    # split into glyphs: a base char plus any variation selector / zero width joiner pieces
    for _g in re.findall(r"[^️‍][️]?", _chars):
        GLYPHS.setdefault(_g.replace("️", ""), _name)

for _d in range(1, 9):  # keycap digits (a digit, VS16, U+20E3); built here because the splitter above would cut them apart
    GLYPHS[f"{_d}⃣"] = f"num_{_d}"

_KEYS = sorted(GLYPHS, key=len, reverse=True)
_PATTERN = re.compile("(?:" + "|".join((re.escape(k[0]) + "️?" + re.escape(k[1:])) if len(k) == 2 and k[1] == "⃣" else re.escape(k) for k in _KEYS) + ")️?")


def _name(glyph: str) -> str | None:
    return GLYPHS.get(glyph.replace("️", ""))


def custom_for(glyph: str) -> str | None:
    """The custom-emoji mention that replaces `glyph`, or None if there is no mapping or it is not uploaded."""
    name = _name(glyph)
    if name is None:
        return None
    found = emojis.get(name[1:]) if name.startswith("@") else emojis.icon(name)
    return found if found and found.startswith("<") else None


def swap(text: str, budget: list[int] | None = None) -> str:
    """`text` with every glyph that has an uploaded icon turned into that icon.

    `budget` (a one-item list: spare characters) caps how much longer the text may grow: once spent, the remaining glyphs stay plain.
    """
    if not text:
        return text

    def one(m: re.Match[str]) -> str:
        custom = custom_for(m.group(0))
        if not custom:
            return m.group(0)
        if budget is not None:
            grow = len(custom) - len(m.group(0))
            if grow > budget[0]:
                return m.group(0)
            budget[0] -= grow
        return custom

    return _PATTERN.sub(one, text)


def strip(text: str) -> str:
    """`text` without the glyphs that have an uploaded icon (for places custom emoji cannot show: labels, descriptions, placeholders)."""
    if not text:
        return text
    out = _PATTERN.sub(lambda m: "" if custom_for(m.group(0)) else m.group(0), text)
    return re.sub(r"[ \t]{2,}", " ", out).strip() if out != text else text


def _emoji_dict(mention: str) -> dict[str, Any]:
    m = re.fullmatch(r"<(a?):(\w+):(\d+)>", mention)
    return {"id": m.group(3), "name": m.group(2), "animated": bool(m.group(1))}


def _plain_glyph(emoji: Any) -> str | None:
    if isinstance(emoji, dict) and not emoji.get("id") and isinstance(emoji.get("name"), str):
        return emoji["name"]
    return None


def _walk(obj: Any, text: list[int] | None) -> Any:
    """A copy of a Discord message payload with glyphs swapped. `text` is the growth budget for message text (see `swap`)."""
    if isinstance(obj, list):
        return [_walk(v, text) for v in obj]
    if not isinstance(obj, dict):
        return obj
    out: dict[str, Any] = {}
    for key, value in obj.items():
        if key == "embeds" and isinstance(value, list):
            out[key] = [_embed(e, text) if isinstance(e, dict) else e for e in value]
        elif key == "emoji" and (g := _plain_glyph(value)) is not None:
            custom = custom_for(g)
            out[key] = _emoji_dict(custom) if custom else value
        elif key == "content" and isinstance(value, str):
            out[key] = swap(value, text)
        elif (key in ("label", "placeholder", "description") or (key == "title" and "custom_id" in obj)) and isinstance(value, str):
            out[key] = strip(value)
        else:
            out[key] = _walk(value, text)
    # a button or select option whose label starts with a glyph: the glyph becomes the component's emoji
    label = obj.get("label")
    if isinstance(label, str) and ("style" in obj or "value" in obj) and not obj.get("emoji"):
        m = _PATTERN.match(label)
        rest = label[m.end():].strip() if m else ""
        if m and (rest or "style" in obj) and (custom := custom_for(m.group(0))):
            out["emoji"] = _emoji_dict(custom)
            if rest:
                out["label"] = strip(rest)
            else:  # an icon-only button: Discord wants no empty label
                out.pop("label")
    return out


def _embed(e: dict[str, Any], text: list[int] | None) -> dict[str, Any]:
    out = dict(e)
    for key in ("title", "description"):
        if isinstance(e.get(key), str):
            out[key] = swap(e[key], text)
    out["fields"] = [
        {**f, "name": swap(f.get("name", ""), text), "value": swap(f.get("value", ""), text)}
        for f in e.get("fields", [])
    ] if "fields" in e else None
    if out["fields"] is None:
        del out["fields"]
    for key in ("footer", "author"):
        if isinstance(e.get(key), dict):
            field = "text" if key == "footer" else "name"
            out[key] = {**e[key], field: strip(e[key].get(field, ""))}
    return out


def _text_size(obj: Any) -> int:
    if isinstance(obj, list):
        return sum(_text_size(v) for v in obj)
    if isinstance(obj, dict):
        return sum(len(v) if k in ("content", "description", "value") and isinstance(v, str) else _text_size(v) for k, v in obj.items())
    return 0


# Discord counts the full ``<:name:id>`` mention, so a very glyph-heavy panel can swell past its limit: then it keeps its plain glyphs.
_TEXT_LIMIT = 3900


def convert(payload: Any) -> Any:
    """The payload with glyphs swapped for our icons (see the module doc). Never makes a message too long to send: when the
    icons would not all fit, the later glyphs stay plain."""
    return _walk(payload, [max(0, _TEXT_LIMIT - _text_size(payload))])


_installed = False


def install() -> None:
    """Hook discord.py's HTTP layer once, so every message the bot sends goes through `convert`."""
    global _installed
    if _installed:
        return
    import discord.http as http

    from discord.webhook.async_ import AsyncWebhookAdapter

    def parts(form):
        return [
            {**part, "value": json.dumps(convert(json.loads(part["value"])))} if part.get("name") == "payload_json" else part
            for part in form
        ]

    # Button clicks and slash replies (interaction callbacks, followups, edit-original) use the webhook adapter, not the HTTP client.
    original_hook = AsyncWebhookAdapter.request

    async def hook_request(self, route, session, *, payload=None, multipart=None, **kwargs):
        if isinstance(payload, (dict, list)):
            payload = convert(payload)
        if multipart:
            multipart = parts(multipart)
        return await original_hook(self, route, session, payload=payload, multipart=multipart, **kwargs)

    AsyncWebhookAdapter.request = hook_request  # type: ignore[method-assign]

    original = http.HTTPClient.request

    async def request(self, route, *, files=None, form=None, **kwargs):
        path = getattr(route, "path", "")
        if any(p in path for p in ("/messages", "/callback", "/webhooks/", "/threads")):
            if "json" in kwargs and isinstance(kwargs["json"], (dict, list)):
                kwargs["json"] = convert(kwargs["json"])
            if form:
                form = parts(form)
        return await original(self, route, files=files, form=form, **kwargs)

    http.HTTPClient.request = request  # type: ignore[method-assign]
    _installed = True
