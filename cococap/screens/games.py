"""Shared plumbing for the in-window casino games."""

import random

import discord

from cococap import constants, emojis
from cococap.services import blackjack, highlow
from cococap.ui import Screen
from cococap.ui.components import bits, button, row


def currency_label(currency: str) -> str:
    return "bits" if currency == "purse" else currency


async def start_game(screen: Screen, interaction: discord.Interaction, game: str, bet_text: str) -> None:
    """Take the bet and show the game screen. A bad or unaffordable bet raises (nothing is taken)."""
    service = highlow if game == "highlow" else blackjack
    state = await service.start(screen.user, bet_text, random.Random(), constants.CASINO_CURRENCY)
    await screen.go(interaction, game, game=state, bet_text=bet_text)


def result_buttons(screen, game_id: str) -> discord.ui.ActionRow:
    """Shown when a hand is over: play again with the same bet, or head back to the casino."""
    async def again(interaction: discord.Interaction) -> None:
        await start_game(screen, interaction, game_id, screen.bet_text)

    async def to_casino(interaction: discord.Interaction) -> None:
        await screen.go(interaction, "casino")

    return row(
        button("Play again", emoji=emojis.icon("again", "🔁"), style=discord.ButtonStyle.primary, on_click=again),
        button("Casino", emoji=emojis.icon("money", "🎰"), on_click=to_casino),
    )


def money(amount: int) -> str:
    return f"{bits(amount)} {currency_label(constants.CASINO_CURRENCY)}"


def reward_line(reward) -> str:
    """One line describing a minigame payout (or why there wasn't one)."""
    if reward is None:
        return ""
    if reward.granted == 0:
        return f"{emojis.icon('luckbucks', '🍀')} You've hit today's minigame limit, so no luckbucks this time. Streaks still count!"
    line = f"**+{emojis.luckbucks(reward.granted)}**"
    if reward.streak_bonus:
        line += f" (streak bonus +{reward.streak_bonus:.0%})"
    if reward.capped:
        line += " — that's today's limit"
    return line


def streak_line(outcome) -> str:
    if outcome.result == "correct":
        return f"Streak: **{outcome.streak}**" + (f"  {emojis.icon('medal', '🏅')} new record!" if outcome.new_record else "")
    return f"You lost a streak of {outcome.lost_streak}." if outcome.lost_streak else ""
