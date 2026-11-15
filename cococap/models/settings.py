from pydantic import BaseModel


class Settings(BaseModel):
    """Per-player options (the Settings page lists them; each saves the moment you press it)."""

    confirm_sell_all: bool = True  # ask "are you sure?" before a Sell all button sells everything from a skill
    keep_upgrade_materials: bool = True  # Sell all always holds back what your next tool upgrades need
    confirm_upgrades: bool = False  # tool upgrades take a second press ("Sure?") so a costly or one-way upgrade is never an accident
    fishing_estimate: bool = True  # show the rod's usual wait for a bite on the Fishing page
