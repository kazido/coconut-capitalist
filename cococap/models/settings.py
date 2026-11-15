from pydantic import BaseModel


class Settings(BaseModel):
    """Per-player options (the Settings page lists them; each saves the moment you press it)."""

    confirm_sell_all: bool = True  # ask "are you sure?" before a Sell all button sells everything from a skill
