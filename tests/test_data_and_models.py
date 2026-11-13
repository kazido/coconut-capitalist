import importlib
import os
import pkgutil

import pytest

import cococap.exts
from cococap.constants import DISABLED_EXTENSIONS
from cococap.models.skills.farming import Farm, Farming


def test_nested_skill_defaults_are_independent():
    a, b = Farming(), Farming()
    a.farm.plot_1.crop_id = "wheat"
    assert b.farm.plot_1.crop_id is None
    assert Farm().plot_9.unlocked is False


def _extension_modules():
    for info in pkgutil.walk_packages(cococap.exts.__path__, "cococap.exts."):
        if not info.ispkg and info.name not in DISABLED_EXTENSIONS:
            yield info.name


@pytest.mark.parametrize("module", sorted(_extension_modules()))
def test_every_enabled_extension_imports(module):
    """Catches the kind of breakage the Mongo migration left behind (renamed/removed names)."""
    importlib.import_module(module)
