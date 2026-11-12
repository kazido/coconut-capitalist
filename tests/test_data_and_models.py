import importlib
import os
import pkgutil

import pytest

import cococap.exts
from cococap.constants import DISABLED_EXTENSIONS
from cococap.models.models import UserDocument
from cococap.models.skills.farming import Farm
from configs.converters.data_converter import fetch, fetch_optional


def test_fetch_works_from_any_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # used to look for ./game_data relative to the cwd
    assert fetch("ranks.1").display_name == "Peasant"
    assert fetch("items.apple.seed").name == "Apple Seed"  # section names may contain dots


def test_fetch_errors():
    with pytest.raises(KeyError):
        fetch("ranks.9999")
    with pytest.raises(FileNotFoundError):
        fetch("nope.1")
    with pytest.raises(ValueError):
        fetch("ranks")
    assert fetch_optional("ranks.9999") is None


def test_new_user_defaults_are_independent(db):
    a, b = UserDocument(name="a", discord_id=1), UserDocument(name="b", discord_id=2)
    a.farming.farm.plot_1.crop_id = "wheat"
    a.items["x"] = {"quantity": 1}
    assert b.farming.farm.plot_1.crop_id is None
    assert b.items == {}
    assert Farm().plot_9.unlocked is False


def _extension_modules():
    for info in pkgutil.walk_packages(cococap.exts.__path__, "cococap.exts."):
        if not info.ispkg and info.name not in DISABLED_EXTENSIONS:
            yield info.name


@pytest.mark.parametrize("module", sorted(_extension_modules()))
def test_every_enabled_extension_imports(module):
    """Catches the kind of breakage the Mongo migration left behind (renamed/removed names)."""
    importlib.import_module(module)
