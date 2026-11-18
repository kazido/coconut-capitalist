"""Deletes the bot's old messages from the play channels, on startup and every few minutes, plus an owner-only /cleanup."""

import asyncio
from datetime import datetime, timezone
from logging import getLogger

import discord
from discord import Interaction, app_commands, ui
from discord.ext import commands, tasks

from cococap.constants import OWNER_ID
from cococap.services.janitor import JanitorConfig, can_bulk, idle_minutes, load_config, should_delete

log = getLogger("janitor")


def _age_minutes(message: discord.Message) -> float:
    """Minutes since the message was last touched (edits count), so a menu in use is not deleted from under a player."""
    return idle_minutes(message.created_at, message.edited_at, datetime.now(timezone.utc))


def _created_days(message: discord.Message) -> float:
    """Days since the message was POSTED. Discord's 14-day bulk-delete limit counts from posting, not from the last edit."""
    return (datetime.now(timezone.utc) - message.created_at).total_seconds() / 86400


async def collect(channel, bot_id: int, limit: float) -> list[discord.Message]:
    """The bot's messages in `channel` untouched for `limit` minutes (0 = all of them)."""
    return [m async for m in channel.history(limit=None) if should_delete(idle=_age_minutes(m), from_bot=m.author.id == bot_id, limit=limit)]


async def delete_all(channel, messages: list[discord.Message], cfg: JanitorConfig) -> int:
    """Bulk delete the recent ones; delete the rest one by one, slowly."""
    recent = [m for m in messages if can_bulk(_created_days(m))]
    old = [m for m in messages if m not in recent]
    done = 0
    for i in range(0, len(recent), 100):
        chunk = recent[i : i + 100]
        if len(chunk) == 1:
            old.append(chunk[0])
            continue
        await channel.delete_messages(chunk)
        done += len(chunk)
        await asyncio.sleep(cfg.delete_delay_seconds)
    for m in old:
        try:
            await m.delete()
            done += 1
        except discord.NotFound:
            pass
        await asyncio.sleep(cfg.delete_delay_seconds)
    return done


class ConfirmView(ui.View):
    def __init__(self, cfg: JanitorConfig, plan: dict):
        super().__init__(timeout=120)
        self.cfg, self.plan = cfg, plan

    @ui.button(label="Delete them", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="Cleaning up... this can take a while.", view=None)
        total = 0
        for channel, messages in self.plan.items():
            try:
                total += await delete_all(channel, messages, self.cfg)
            except discord.HTTPException as e:
                log.warning("cleanup failed in %s: %s", channel.id, e)
        await interaction.edit_original_response(content=f"Deleted {total} messages.")

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="Cancelled. Nothing was deleted.", view=None)


class Janitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cfg = load_config()
        self._startup = True  # the first pass after the bot starts deletes EVERY bot message: no menu can still be played after a restart

    async def cog_load(self):
        if self.cfg.enabled:
            self.sweep.change_interval(minutes=self.cfg.interval_minutes)  # the config sets how often, not the decorator
            self.sweep.start()

    async def cog_unload(self):
        self.sweep.cancel()

    @tasks.loop(minutes=5)
    async def sweep(self):
        limit = 0 if self._startup else self.cfg.idle_minutes
        self._startup = False
        for cid in self.cfg.channel_ids:
            channel = self.bot.get_channel(cid)
            if channel is None:
                continue
            try:
                messages = await collect(channel, self.bot.user.id, limit)
                if messages:
                    n = await delete_all(channel, messages, self.cfg)
                    log.info("janitor deleted %s message(s) in %s", n, cid)
            except discord.Forbidden:
                log.warning("janitor lacks Manage Messages / Read Message History in %s", cid)
            except Exception:  # noqa: BLE001 - a failed sweep must not stop the loop
                log.exception("janitor sweep failed in %s", cid)

    @sweep.before_loop
    async def _wait(self):
        await self.bot.wait_until_ready()  # the first run is the startup pass

    @app_commands.command(name="cleanup", description="Owner only: delete the bot's old messages in the play channels.")
    @app_commands.describe(dry_run="Only count what would be deleted (default yes).")
    async def cleanup(self, interaction: Interaction, dry_run: bool = True):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        # One-time pass: every bot message goes, whatever its age (limits of 0).
        cfg = JanitorConfig(True, self.cfg.channel_ids, 0, 0, self.cfg.delete_delay_seconds)
        plan, lines = {}, []
        for cid in cfg.channel_ids:
            channel = self.bot.get_channel(cid)
            if channel is None:
                lines.append(f"<#{cid}>: not visible to the bot")
                continue
            try:
                messages = await collect(channel, self.bot.user.id, 0)
            except discord.Forbidden:
                lines.append(f"<#{cid}>: missing Read Message History / Manage Messages")
                continue
            plan[channel] = messages
            old = sum(not can_bulk(_created_days(m)) for m in messages)
            lines.append(f"<#{cid}>: {len(messages)} to delete ({old} older than 14 days, slow)")
        text = "\n".join(lines)
        if dry_run:
            await interaction.followup.send(f"Dry run, nothing deleted:\n{text}\nRun again with dry_run: False.")
        else:
            await interaction.followup.send(f"This will delete:\n{text}", view=ConfirmView(cfg, plan))


async def setup(bot):
    await bot.add_cog(Janitor(bot))
