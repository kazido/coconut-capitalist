"""User-facing exceptions shared across cogs and utilities.

These live outside the ``exts`` package so low-level helpers (bit parsing, checks) can raise them
without importing a cog module.
"""

from discord.app_commands import AppCommandError


class CustomError(AppCommandError):
    """An error whose message is safe to show to the user verbatim."""

    def __init__(self, message, title=None, footer=None):
        super().__init__(message)
        self.title = title
        self.footer = footer


class AlreadyInGame(CustomError):
    pass


class InvalidAmount(CustomError):
    pass


class ButtonCheckFailure(CustomError):
    pass


class GameRuleError(Exception):
    """A game rule was broken (not enough bits, wrong tool, on cooldown ...). The message is written
    for the player and is shown to them as-is; anything else is treated as a bug."""
