import discord
import random

from datetime import datetime
from typing import Any
from discord.colour import Colour
from discord.types.embed import EmbedType
from cococap.constants import SUCCESS_REPLIES, FAILURE_REPLIES, ERROR_REPLIES


class CustomEmbed(discord.Embed):
    def __init__(
        self,
        *,
        color: int | Colour | None = None,
        colour: int | Colour | None = None,
        title: Any | None = None,
        type: EmbedType = "rich",
        url: Any | None = None,
        desc: Any | None = None,
        description: Any | None = None,
        timestamp: datetime | None = None,
        interaction: discord.Interaction | None = None,
        activity: str,
    ):
        if colour is not None:
            color = colour
        if description is not None:
            desc = description
        super().__init__(
            color=color,
            title=title,
            type=type,
            url=url,
            description=desc,
            timestamp=timestamp,
        )
        if interaction:
            self.set_author(
                name=f"{interaction.user.display_name} - {activity}",
                icon_url=interaction.user.display_avatar,
            )


class SuccessEmbed(CustomEmbed):
    def __init__(
        self,
        *,
        color=0xA0F09C,
        title=random.choice(SUCCESS_REPLIES),
        type="rich",
        url=None,
        desc="I don't know *what* we're happy about, but **LET'S GO!**",
        timestamp=None,
        interaction=None,
        activity=":D",
    ):

        super().__init__(
            color=color,
            title=title,
            type=type,
            url=url,
            desc=desc,
            timestamp=timestamp,
            interaction=interaction,
            activity=activity,
        )


class FailureEmbed(CustomEmbed):
    def __init__(
        self,
        *,
        color=discord.Color.dark_gray(),
        title=random.choice(FAILURE_REPLIES),
        type="rich",
        url=None,
        desc="Something goofed! Not sure what it is though...",
        timestamp=None,
        interaction=None,
        activity=":(",
    ):

        super().__init__(
            color=color,
            title=title,
            type=type,
            url=url,
            desc=desc,
            timestamp=timestamp,
            interaction=interaction,
            activity=activity,
        )


class ErrorEmbed(CustomEmbed):
    def __init__(
        self,
        *,
        color=discord.Color.red(),
        title=None,
        type="rich",
        url=None,
        desc="Error! Check logs!",
        timestamp=None,
        interaction=None,
        activity=":/",
    ):
        if title is None:
            title = random.choice(ERROR_REPLIES)

        super().__init__(
            color=color,
            title=title,
            type=type,
            url=url,
            desc=desc,
            timestamp=timestamp,
            interaction=interaction,
            activity=activity,
        )
