"""Lifesteal commands cog."""

import discord
from discord.ext import commands

from ..api import PIGDIClient
from ..config import config
from ..embeds import stat_emojis, stat_to_embed


class Lifesteal(commands.Cog):
    """Lifesteal-related commands."""

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.client = PIGDIClient(config.ARCH_API_KEY)

    @discord.slash_command(
        name="lifetop",
        description="Show the top players for a selected Lifesteal stat",
    )
    @discord.option(
        "stat",
        str,
        description="Select the statistic",
        choices=[
            "kills",
            "deaths",
            "killstreak",
            "killDeathRatio",
            "blocksMined",
            "blocksWalked",
            "blocksPlaced",
        ],
        required=True,
    )
    async def lifetop(self, ctx: discord.ApplicationContext, stat: str) -> None:
        await ctx.defer()
        try:
            leaderboard = self.client.get_ugc_leaderboard("trojan", stat)
            if leaderboard and "entries" in leaderboard:
                leaderboard_lines = [
                    f"**#{entry.get('position', i + 1)}** "
                    f"{entry.get('username', 'Unknown')} — `{entry.get('value', 0)}`"
                    for i, entry in enumerate(leaderboard["entries"])
                ]
                leaderboard_text = "\n".join(leaderboard_lines)
                embed = discord.Embed(
                    title=f"🏆 Lifesteal Top {stat.capitalize()}",
                    description=leaderboard_text,
                    color=discord.Color.red(),
                )
                embed.set_footer(text="ArchMC Lifesteal • Official API")
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No leaderboard data found.")
        except Exception as e:
            await ctx.respond(f"Failed to fetch leaderboard: {e}")

    @discord.slash_command(
        name="lifestats",
        description="Show all Lifesteal stats and profile for a player",
    )
    @discord.option(
        "username",
        str,
        description="Minecraft username",
        required=True,
    )
    async def lifestats(self, ctx: discord.ApplicationContext, username: str) -> None:
        await ctx.defer()
        try:
            username_lower = username.lower()
            stats = self.client._request(
                "GET", f"/v1/ugc/trojan/players/username/{username_lower}/statistics"
            )
            profile = self.client._request(
                "GET", f"/v1/ugc/trojan/players/username/{username_lower}/profile"
            )

            if stats and isinstance(stats, dict):
                username_disp = stats.get("username", username)
                statistics = stats.get("statistics", {})

                embed = discord.Embed(
                    title=f"📊 Lifesteal Stats for {username_disp}",
                    color=discord.Color.red(),
                )

                for k, v in statistics.items():
                    emoji = stat_emojis.get(k, "📈")
                    name = f"{emoji} {k.capitalize()}"
                    value_lines = []
                    if isinstance(v, dict) and "value" in v:
                        value_lines.append(f"Value: `{v.get('value', 0)}`")
                        if v.get("position") is not None:
                            value_lines.append(f"Rank: `#{v.get('position'):,}`")
                        if v.get("percentile") is not None:
                            value_lines.append(
                                f"Percentile: Top {100 - float(v.get('percentile')):.2f}%"
                            )
                    else:
                        value_lines.append(f"Value: `{v}`")
                    embed.add_field(name=name, value="\n".join(value_lines), inline=True)

                if profile and isinstance(profile, dict):
                    profile_lines = []
                    for k, v in profile.items():
                        if k in ("username", "uuid") or isinstance(v, (dict, list)):
                            continue
                        label = k.replace("_", " ").capitalize()
                        if k.lower() == "totalplaytimeseconds" and isinstance(
                            v, (int, float)
                        ):
                            hours = v // 3600
                            days = hours // 24
                            label = "Total Playtime"
                            value_str = f"{int(hours):,} hours ({int(days):,} days)"
                        else:
                            value_str = v
                        profile_lines.append(f"**{label}**: `{value_str}`")
                    if profile_lines:
                        embed.add_field(
                            name="Profile Info",
                            value="\n".join(profile_lines),
                            inline=False,
                        )

                embed.set_footer(text="ArchMC Lifesteal • Official API")
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No stats found for that player.")
        except Exception as e:
            await ctx.respond(f"Failed to fetch stats: {e}")

    @discord.slash_command(
        name="lifestat",
        description="Show a specific Lifesteal stat for a player",
    )
    @discord.option(
        "username",
        str,
        description="Minecraft username",
        required=True,
    )
    @discord.option(
        "stat",
        str,
        description="Select the statistic",
        choices=[
            "kills",
            "deaths",
            "killstreak",
            "killDeathRatio",
            "blocksMined",
            "blocksWalked",
            "blocksPlaced",
        ],
        required=True,
    )
    async def lifestat(
        self, ctx: discord.ApplicationContext, username: str, stat: str
    ) -> None:
        await ctx.defer()
        try:
            username_lower = username.lower()
            stat_info = self.client._request(
                "GET",
                f"/v1/ugc/trojan/players/username/{username_lower}/statistics/{stat}",
            )

            if stat_info and isinstance(stat_info, dict) and "value" in stat_info:
                embed = stat_to_embed(stat_info, stat, username)
                await ctx.respond(embed=embed)
            else:
                stats = self.client.get_ugc_player_stats_by_username(
                    "trojan", username_lower
                )
                stat_val = (
                    stats["statistics"].get(stat)
                    if stats and "statistics" in stats and stat in stats["statistics"]
                    else None
                )
                if stat_val is not None:
                    if not isinstance(stat_val, dict):
                        stat_val = {"value": stat_val}
                    embed = stat_to_embed(stat_val, stat, username)
                    await ctx.respond(embed=embed)
                else:
                    await ctx.respond("No data found for that player/stat.")
        except Exception as e:
            await ctx.respond(f"Failed to fetch stat: {e}")


def setup(bot: discord.Bot) -> None:
    bot.add_cog(Lifesteal(bot))
