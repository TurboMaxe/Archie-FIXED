"""Duels commands cog."""

import logging
import traceback
from collections import defaultdict

import discord
import requests
from discord.ext import commands

from ..config import config
from ..embeds import build_duelstats_embed, mode_labels
from ..views import DuelStatsView

logger = logging.getLogger("archie-bot")


class Duels(commands.Cog):
    """Duels-related commands."""

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @discord.slash_command(
        name="dueltop",
        description="Show the top players for a selected Duel stat",
    )
    @discord.option(
        "statid",
        str,
        description="Select the duel stat",
        choices=[
            "elo:nodebuff:ranked:lifetime",
            "elo:sumo:ranked:lifetime",
            "elo:bridge:ranked:lifetime",
            "wins:nodebuff:ranked:lifetime",
            "wins:sumo:ranked:lifetime",
            "wins:bridge:ranked:lifetime",
        ],
        required=True,
    )
    async def dueltop(self, ctx: discord.ApplicationContext, statid: str) -> None:
        await ctx.defer()
        try:
            url = f"https://api.arch.mc/v1/leaderboards/{statid}?page=0&size=10"
            headers = {"X-API-KEY": config.ARCH_API_KEY}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                entries = data.get("entries") or data.get("leaderboard") or []
                if isinstance(entries, list) and entries:
                    leaderboard_lines = [
                        f"**#{entry.get('position', i + 1)}** "
                        f"{entry.get('username', 'Unknown')} — `{entry.get('value', 0)}`"
                        for i, entry in enumerate(entries)
                    ]
                    leaderboard_text = "\n".join(leaderboard_lines)
                    embed = discord.Embed(
                        title=f"🥊 Duel Top: {statid}",
                        description=leaderboard_text,
                        color=discord.Color.blue(),
                    )
                    embed.set_footer(text="ArchMC Duels • Official API")
                    await ctx.respond(embed=embed)
                else:
                    await ctx.respond("No duel leaderboard data found.")
            else:
                await ctx.respond(
                    f"Failed to fetch duel leaderboard. Status code: {response.status_code}"
                )
        except Exception as e:
            await ctx.respond(f"Failed to fetch duel leaderboard: {e}")

    @discord.slash_command(
        name="duelstats",
        description="Show all duel stats for a player",
    )
    @discord.option(
        "username",
        str,
        description="Minecraft username",
        required=True,
    )
    async def duelstats(self, ctx: discord.ApplicationContext, username: str) -> None:
        await ctx.defer()
        try:
            url = f"https://api.arch.mc/v1/players/username/{username.lower()}/statistics"
            headers = {"X-API-KEY": config.ARCH_API_KEY}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                statistics = data.get("statistics", {})
                duel_stats = {
                    k: v
                    for k, v in statistics.items()
                    if k.startswith("elo:") or k.startswith("wins:")
                }
                logger.info(
                    f"[duelstats] username={username} duel_stats_keys={list(duel_stats.keys())}"
                )

                if duel_stats:
                    try:
                        mode_stats = defaultdict(lambda: {"ELO": [], "WINS": []})
                        for k, v in duel_stats.items():
                            parts = k.split(":")
                            if len(parts) >= 2:
                                stat_type = parts[0].upper()
                                mode = parts[1].lower()
                                context = ":".join(parts[2:]) if len(parts) > 2 else ""
                                if stat_type == "ELO":
                                    mode_stats[mode]["ELO"].append((context, v))
                                elif stat_type == "WINS":
                                    mode_stats[mode]["WINS"].append((context, v))
                                else:
                                    if stat_type not in mode_stats[mode]:
                                        mode_stats[mode][stat_type] = []
                                    mode_stats[mode][stat_type].append((context, v))
                            else:
                                if "OTHER" not in mode_stats["other"]:
                                    mode_stats["other"]["OTHER"] = []
                                mode_stats["other"]["OTHER"].append((k, v))

                        mode_keys = sorted(mode_stats.keys())
                        page = 0
                        embed = build_duelstats_embed(
                            data, username, mode_stats, mode_keys, page, 4
                        )
                        view = DuelStatsView(
                            data, username, mode_stats, mode_keys, page
                        )
                        await ctx.respond(embed=embed, view=view)
                    except Exception as group_exc:
                        logger.error(
                            f"[duelstats] Grouping error for {username}: {group_exc}\n"
                            f"{traceback.format_exc()}"
                        )
                        await ctx.respond("Failed to format duel stats.")
                else:
                    await ctx.respond("No duel stats found for that player.")
            else:
                await ctx.respond(
                    f"Failed to fetch duel stats. Status code: {response.status_code}"
                )
        except Exception as e:
            logger.error(
                f"[duelstats] Exception for {username}: {e}\n{traceback.format_exc()}"
            )
            await ctx.respond(f"Failed to fetch duel stats: {e}")


def setup(bot: discord.Bot) -> None:
    bot.add_cog(Duels(bot))
