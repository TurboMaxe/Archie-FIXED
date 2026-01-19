"""Miscellaneous commands cog."""

import discord
import requests
from discord.ext import commands

from ..api import PIGDIClient
from ..config import config


class Misc(commands.Cog):
    """Miscellaneous commands."""

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.client = PIGDIClient(config.ARCH_API_KEY)

    @discord.slash_command(
        name="playtime",
        description="Show the playtime leaderboard for a selected mode",
    )
    @discord.option(
        "mode",
        str,
        description="Select the server mode",
        choices=["lifesteal", "survival"],
        required=True,
    )
    async def playtime(self, ctx: discord.ApplicationContext, mode: str) -> None:
        await ctx.defer()
        try:
            gamemode = "trojan" if mode == "lifesteal" else "spartan"
            leaderboard = self.client._request(
                "GET", f"/v1/ugc/{gamemode}/leaderboard/playtime?page=0&size=10"
            )
            entries = (
                leaderboard.get("entries")
                or leaderboard.get("players")
                or leaderboard.get("leaderboard")
                or []
                if leaderboard
                else []
            )

            if isinstance(entries, list) and entries:
                leaderboard_lines = []
                for i, entry in enumerate(entries):
                    username = entry.get("username") or entry.get("name") or "Unknown"
                    playtime = (
                        entry.get("value")
                        or entry.get("playtime")
                        or entry.get("hours")
                    )
                    if isinstance(playtime, (int, float)) and playtime > 10000:
                        playtime = round(playtime / 3600, 1)
                    leaderboard_lines.append(
                        f"**#{entry.get('position', i + 1)}** {username} — `{playtime} hours`"
                    )

                leaderboard_text = "\n".join(leaderboard_lines)
                color = discord.Color.red() if mode == "lifesteal" else discord.Color.green()
                embed = discord.Embed(
                    title=f"⏱️ {mode.capitalize()} Playtime Top",
                    description=leaderboard_text,
                    color=color,
                )
                embed.set_footer(text=f"ArchMC {mode.capitalize()} • Official API")
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No leaderboard data found.")
        except Exception as e:
            await ctx.respond(f"Failed to fetch playtime leaderboard: {e}")

    @discord.slash_command(
        name="clantop",
        description="Show the top clans from ArchMC",
    )
    async def clantop(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer()
        try:
            url = "https://api.arch.mc/v1/ugc/trojan/clans?page=0&size=10"
            headers = {"X-API-KEY": config.ARCH_API_KEY}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                clans = (
                    data.get("clans")
                    or data.get("entries")
                    or data.get("leaderboard")
                    or []
                )

                if isinstance(clans, list) and clans:
                    leaderboard_lines = []
                    for i, clan in enumerate(clans):
                        name = (
                            clan.get("name")
                            or clan.get("clanName")
                            or clan.get("clan")
                            or "Unknown"
                        )
                        level = clan.get("level")
                        if level is None:
                            exp = clan.get("experience")
                            if exp is not None:
                                try:
                                    level = int(exp) // 1000
                                except Exception:
                                    level = exp
                            else:
                                level = (
                                    clan.get("points")
                                    or clan.get("score")
                                    or clan.get("value")
                                    or 0
                                )
                        leaderboard_lines.append(f"**#{i + 1} {name}** — Level {level}")

                    leaderboard_text = "\n".join(leaderboard_lines)
                    embed = discord.Embed(
                        title="🏅 Top Clans",
                        description=leaderboard_text,
                        color=discord.Color.gold(),
                    )
                    embed.set_footer(text="ArchMC Clans • Official API")
                    await ctx.respond(embed=embed)
                else:
                    await ctx.respond("No clan leaderboard data found.")
            else:
                await ctx.respond(
                    f"Failed to fetch clan leaderboard. Status code: {response.status_code}"
                )
        except Exception as e:
            await ctx.respond(f"Failed to fetch clan leaderboard: {e}")

    @discord.slash_command(
        name="invite",
        description="Get the invite link for Archie",
    )
    async def invite(self, ctx: discord.ApplicationContext) -> None:
        invite_url = (
            "https://discord.com/oauth2/authorize"
            "?client_id=1454187186651009116"
            "&permissions=6144"
            "&scope=bot%20applications.commands"
        )
        support_url = "https://discord.gg/pzSYrhBCA5"
        embed = discord.Embed(
            title="Invite Archie to your server!",
            description=(
                f"➕ [Click here to invite Archie]({invite_url})\n"
                f"💬 [Join the support server]({support_url})\n\n"
                "Add Archie to your server and join our support community for help and updates."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Thank you for supporting Archie!")
        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="help",
        description="Show help for Archie commands",
    )
    async def help(self, ctx: discord.ApplicationContext) -> None:
        embed = discord.Embed(
            title="Archie Help",
            description="**Here are all available commands:**",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="/playtime",
            value="⏱️ Show the playtime leaderboard for Lifesteal or Survival.",
            inline=False,
        )
        embed.add_field(
            name="/lifetop",
            value="🏆 Show the top players for a selected Lifesteal stat.",
            inline=False,
        )
        embed.add_field(
            name="/lifestats",
            value="📊 Show all Lifesteal stats and profile for a player (card style).",
            inline=False,
        )
        embed.add_field(
            name="/lifestat",
            value="📈 Show a specific Lifesteal stat for a player, with value, rank, and percentile.",
            inline=False,
        )
        embed.add_field(
            name="/dueltop",
            value="🥊 Show the top players for a selected Duel stat (ELO or Wins).",
            inline=False,
        )
        embed.add_field(
            name="/duelstats",
            value="🎴 Show all Duel stats for a player, grouped and paginated (card style).",
            inline=False,
        )
        embed.add_field(
            name="/balance",
            value="💰 Show a player's balance for a selected gamemode.",
            inline=False,
        )
        embed.add_field(
            name="/baltop",
            value="🏦 Show the baltop leaderboard for a selected currency or experience type.",
            inline=False,
        )
        embed.add_field(
            name="/clantop",
            value="🏅 Show the top clans from ArchMC.",
            inline=False,
        )
        embed.add_field(
            name="/invite",
            value="➕ Get the invite link for Archie and the support server.",
            inline=False,
        )
        embed.set_footer(text="More commands and features coming soon! | Archie by ArchMC")
        await ctx.respond(embed=embed)


def setup(bot: discord.Bot) -> None:
    bot.add_cog(Misc(bot))
