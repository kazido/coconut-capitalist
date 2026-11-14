from pydantic import BaseModel


class Settings(BaseModel):
    """Per-player options. None yet (the old auto-deposit went away with the bank)."""
