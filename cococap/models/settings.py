from pydantic import BaseModel


class Settings(BaseModel):
    """Per-player options (the Settings page lists them; each saves the moment you press it)."""

    confirm_upgrades: bool = False  # tool upgrades take a second press ("Sure?") so a costly or one-way upgrade is never an accident
    fishing_estimate: bool = True  # show the rod's usual wait for a bite on the Fishing page
    auto_craft: bool = False  # the Workbench also makes missing craftable inputs (like the previous fuel) from raw materials
    zones: dict[str, str] = {}  # where you last set each skill's location (mining/fishing/foraging); sticks until you change it
    seen_notices: list[str] = []  # ids of the notices (configs/notices.toml) already popped up for this player; each shows once
