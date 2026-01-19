"""Economy commands cog."""

import discord
import requests
from discord.ext import commands

from ..config import config


class Economy(commands.Cog):
    """Economy-related commands."""

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @discord.slash_command(
        name="balance",
        description="Show a player's balance for a selected gamemode",
    )
    @discord.option(
        "gamemode",
        str,
        description="Select the gamemode",
        choices=["lifesteal", "survival", "bedwars", "kitpvp", "skywars"],
        required=True,
    )
    @discord.option(
        "username",
        str,
        description="Minecraft username",
        required=True,
    )
    async def balance(
        self, ctx: discord.ApplicationContext, gamemode: str, username: str
    ) -> None:
        await ctx.defer()
        try:
            username_lower = username.lower()
            type_map = {
                "lifesteal": "lifesteal-coins",
                "survival": "gems",
                "bedwars": "bedwars-coins",
                "kitpvp": "kitpvp-coins",
                "skywars": "skywars-coins",
            }
            bal_type = type_map.get(gamemode)
            if not bal_type:
                await ctx.respond("Invalid gamemode selected.")
                return

            url = f"https://api.arch.mc/v1/economy/player/username/{username_lower}"
            headers = {"X-API-KEY": config.ARCH_API_KEY}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                balances = data.get("balances", {})
                if not balances:
                    await ctx.respond(
                        f"No balance data found for {username}. "
                        "The player may not have played any supported gamemode yet."
                    )
                    return

                if bal_type in balances:
                    balance = balances[bal_type]
                    embed = discord.Embed(
                        title=f"💰 {gamemode.capitalize()} Balance for {username}",
                        description=f"**{balance:,}**",
                        color=discord.Color.gold(),
                    )
                    embed.set_footer(text=f"ArchMC {gamemode.capitalize()} • Official API")
                    await ctx.respond(embed=embed)
                else:
                    bal_lines = [
                        f"**{k.replace('-', ' ').title()}**: `{v:,}`"
                        for k, v in balances.items()
                    ]
                    embed = discord.Embed(
                        title=f"💰 All Balances for {username}",
                        description="\n".join(bal_lines),
                        color=discord.Color.gold(),
                    )
                    embed.set_footer(text="ArchMC Economy • Official API")
                    await ctx.respond(
                        content=f"No {gamemode} balance found for {username}. Showing all available balances:",
                        embed=embed,
                    )
            elif response.status_code == 404:
                await ctx.respond(
                    f"No balance profile found for **{username}**. "
                    "The player may not exist or has never played on ArchMC."
                )
            else:
                await ctx.respond(
                    f"Failed to fetch balance for {username} in {gamemode}. "
                    f"(Status code: {response.status_code})"
                )
        except Exception as e:
            await ctx.respond(f"Failed to fetch balance: {e}")

    @discord.slash_command(
        name="baltop",
        description="Show the baltop leaderboard for a selected type",
    )
    @discord.option(
        "type",
        str,
        description="Select the baltop type",
        choices=[
            "lifesteal-coins",
            "bedwars-coins",
            "kitpvp-coins",
            "gems",
            "bedwars-experience",
            "skywars-coins",
            "skywars-experience",
        ],
        required=True,
    )
    async def baltop(self, ctx: discord.ApplicationContext, type: str) -> None:
        await ctx.defer()
        try:
            url = f"https://api.arch.mc/v1/economy/baltop/{type}"
            headers = {"X-API-KEY": config.ARCH_API_KEY}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                entries = data.get("entries") or []
                if isinstance(entries, list) and entries:
                    leaderboard_lines = [
                        f"**#{entry.get('position', i + 1)}** "
                        f"{entry.get('username', 'Unknown')} — `{entry.get('balance', 0)}`"
                        for i, entry in enumerate(entries)
                    ]
                    leaderboard_text = "\n".join(leaderboard_lines)
                    embed = discord.Embed(
                        title=f"🏦 Baltop Leaderboard: {type.replace('-', ' ').title()}",
                        description=leaderboard_text,
                        color=discord.Color.gold(),
                    )
                    embed.set_footer(text="ArchMC Baltop • Official API")
                    await ctx.respond(embed=embed)
                else:
                    await ctx.respond("No baltop data found for that type.")
            else:
                await ctx.respond(
                    f"Failed to fetch baltop leaderboard. Status code: {response.status_code}"
                )
        except Exception as e:
            await ctx.respond(f"Failed to fetch baltop leaderboard: {e}")


def setup(bot: discord.Bot) -> None:
    bot.add_cog(Economy(bot))
