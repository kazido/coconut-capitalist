"""Read-only access to the game data in ``configs/*.ini``.

``fetch("ranks.3")`` returns an object whose attributes are the (string) values of section ``[3]``
in ``configs/ranks.ini``. Files are parsed once and cached for the life of the process.
"""

import configparser
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent  # <repo>/configs


class _DynamicObject:
    def __init__(self, **attributes):
        for key, value in attributes.items():
            setattr(self, key, value)

    def __repr__(self):
        return "\n".join(f"{key}: {value}" for key, value in self.__dict__.items())


@lru_cache(maxsize=None)
def _load(filename: str) -> configparser.ConfigParser:
    ini_path = CONFIG_DIR / f"{filename}.ini"
    if not ini_path.is_file():
        raise FileNotFoundError(f"INI file '{filename}.ini' not found in '{CONFIG_DIR}'")
    config = configparser.ConfigParser()
    config.read(ini_path)
    return config


def fetch(identifier: str) -> _DynamicObject:
    """Fetch section ``obj_id`` of ``filename.ini`` given ``"filename.obj_id"``.

    Section names may themselves contain dots (``items.apple.seed``), so only the first dot
    separates file from section.
    """
    filename, sep, obj_id = identifier.partition(".")
    if not sep or not obj_id:
        raise ValueError("Identifier must be in the format 'filename.identifier'")

    config = _load(filename)
    if obj_id not in config:
        raise KeyError(f"Identifier '{obj_id}' not found in '{filename}.ini'")
    return _DynamicObject(**dict(config[obj_id].items()))


def fetch_optional(identifier: str) -> "_DynamicObject | None":
    """Like fetch(), but returns None when the section doesn't exist (e.g. the rank after max)."""
    try:
        return fetch(identifier)
    except KeyError:
        return None


if __name__ == "__main__":
    print(fetch("swords.rustedbroadsword"))
