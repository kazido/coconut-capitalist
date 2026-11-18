"""Shared plumbing for the Games page: the bet prompt, the balance line and the payout lines of the games."""

import random

import discord

from cococap import constants, emojis
from cococap.services import blackjack, highlow
from cococap.ui import PromptModal, Screen
from cococap.ui.components import bits, button, row, text


def currency_label(currency: str) -> str:
    return "bits" if currency == "purse" else currency


def casino_intro(user):
    """What the casino stakes, what the player holds and how to type a bet. Shown before a card game's bet."""
    name = currency_label(constants.CASINO_CURRENCY)
    return text(
        f"**{emojis.luckbucks(user.luckbucks)}**  ·  **{emojis.bits(user.purse)}**\n"
        f"The casino stakes **{name}**. Bet a number, `2k`, a percent like `25%`, or `max`."
    )


def ask_bet(screen: Screen, game_id: str, title: str):
    """A Play button's handler: ask for the bet in a modal, then open the game on its own tab."""

    async def ask(interaction: discord.Interaction) -> None:
        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            await start_game(screen, modal_interaction, game_id, raw)

        await interaction.response.send_modal(
            PromptModal(f"{title}: place your bet", "Bet", submitted, default="100", placeholder="100, 2k, 25%, max")
        )

    return ask


async def start_game(screen: Screen, interaction: discord.Interaction, game: str, bet_text: str) -> None:
    """Take the bet and show the game on the Games page. A bad or unaffordable bet raises (nothing is taken)."""
    service = highlow if game == "highlow" else blackjack
    state = await service.start(screen.user, bet_text, random.Random(), constants.CASINO_CURRENCY)
    await screen.go(interaction, "games", tab=game, game=state, bet_text=bet_text)


def result_buttons(screen, game_id: str) -> discord.ui.ActionRow:
    """Shown when a hand is over: play again with the same bet. The hub's Home and Back row is the way out."""

    async def again(interaction: discord.Interaction) -> None:
        await start_game(screen, interaction, game_id, screen.bet_text)

    return row(button("Play again", emoji=emojis.icon("again", "🔁"), style=discord.ButtonStyle.primary, on_click=again))


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
