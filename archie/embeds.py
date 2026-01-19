"""Embed builder functions for Archie bot."""

from typing import Any, Dict, List, Tuple

import discord

stat_emojis: Dict[str, str] = {
    "kills": "⚔️",
    "deaths": "💀",
    "killstreak": "🔥",
    "killDeathRatio": "📊",
    "blocksMined": "⛏️",
    "blocksWalked": "🚶",
    "blocksPlaced": "🧱",
}

mode_labels: Dict[str, Tuple[str, str]] = {
    "boxing": ("🥊", "Boxing"),
    "nodebuff": ("💧", "NoDebuff"),
    "sumo": ("🧍", "Sumo"),
    "bridge": ("🌉", "Bridge"),
    "classic": ("🗡️", "Classic"),
    "combo": ("⚡", "Combo"),
    "builduhc": ("🏗️", "BuildUHC"),
    "spleef": ("⛏️", "Spleef"),
    "fireballfight": ("🔥", "Fireball Fight"),
    "invaded": ("🛡️", "Invaded"),
    "archer": ("🏹", "Archer"),
    "pearl": ("🦪", "Pearl"),
    "stickfight": ("🥢", "Stickfight"),
    "creeper_sumo": ("💣", "Creeper Sumo"),
    "debuff": ("☠️", "Debuff"),
    "gapple": ("🍏", "Gapple"),
    "bw_mega_quads": ("4️⃣", "BW Mega Quads"),
    "bw_mega_trios": ("3️⃣", "BW Mega Trios"),
    "bw_mini_duos": ("2️⃣", "BW Mini Duos"),
    "bw_mini_solo": ("1️⃣", "BW Mini Solo"),
    "bridges": ("🌉", "Bridges"),
    "skywars": ("☁️", "Skywars"),
    "vanilla": ("🍞", "Vanilla"),
    "topfight": ("🔝", "Topfight"),
    "global": ("🌐", "Global"),
    "rswinternal": ("🧪", "RSWInternal"),
    "bedfight": ("🛏️", "BedFight"),
}


def build_duelstats_embed(
    data: Dict[str, Any],
    username: str,
    mode_stats: Dict[str, Dict[str, List[Tuple[str, Any]]]],
    mode_keys: List[str],
    page: int,
    page_size: int = 4,
) -> discord.Embed:
    """
    Build a paginated embed for duel stats.

    Args:
        data: Full player data dictionary.
        username: The player's username.
        mode_stats: Dictionary of mode -> stat type -> list of (context, value) tuples.
        mode_keys: Sorted list of mode keys.
        page: Current page number (0-indexed).
        page_size: Number of modes per page.

    Returns:
        A Discord embed for the current page.
    """
    modes_per_page = page_size
    start = page * modes_per_page
    end = start + modes_per_page
    shown_modes = mode_keys[start:end]

    embed = discord.Embed(
        title=f"Archie — 🥊 Duel Stats for {data.get('username', username)}",
        color=discord.Color.purple(),
        description=f"Page {page + 1} of {((len(mode_keys) - 1) // modes_per_page) + 1}",
    )
    embed.set_thumbnail(
        url="https://cdn.discordapp.com/icons/1454187186651009116/3e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e.png?size=128"
    )

    for mode in shown_modes:
        emoji, label = mode_labels.get(mode, ("❓", mode.capitalize()))

        for context, v in mode_stats[mode]["ELO"]:
            value = v.get("value", 0) if isinstance(v, dict) and "value" in v else v
            context_str = f" ({context})" if context else ""
            stat_name = (
                f"{emoji} {label} ELO{context_str}"
                if context_str
                else f"{emoji} {label} ELO"
            )
            embed.add_field(name=stat_name, value=f"`{value}`", inline=True)

        for context, v in mode_stats[mode]["WINS"]:
            value = v.get("value", 0) if isinstance(v, dict) and "value" in v else v
            context_str = f" ({context})" if context else ""
            stat_name = (
                f"{emoji} {label} Wins{context_str}"
                if context_str
                else f"{emoji} {label} Wins"
            )
            embed.add_field(name=stat_name, value=f"`{value}`", inline=True)

        for stat_type in mode_stats[mode]:
            if stat_type in ("ELO", "WINS"):
                continue
            for context, v in mode_stats[mode][stat_type]:
                value = v.get("value", 0) if isinstance(v, dict) and "value" in v else v
                context_str = f" ({context})" if context else ""
                stat_name = (
                    f"{emoji} {label} {stat_type}{context_str}"
                    if context_str
                    else f"{emoji} {label} {stat_type}"
                )
                embed.add_field(name=stat_name, value=f"`{value}`", inline=True)

    embed.set_footer(text="Archie • ArchMC Duels • Official API")
    return embed


def stat_to_embed(stat: Dict[str, Any], stat_name: str, username: str) -> discord.Embed:
    """
    Format a stat dictionary as a Discord embed.

    Args:
        stat: Dictionary containing stat data (value, position, percentile, etc.).
        stat_name: Name of the statistic.
        username: The player's username.

    Returns:
        A Discord embed displaying the stat.
    """
    emoji = stat_emojis.get(stat_name, "📈")
    value = stat.get("value", stat.get("statValue", 0))
    position = stat.get("position")
    percentile = stat.get("percentile")
    total_players = stat.get("totalPlayers")

    embed = discord.Embed(
        title=f"{emoji} {stat_name.capitalize()} — {username}",
        description=f"**{value}**",
        color=discord.Color.red(),
    )

    if position is not None:
        embed.add_field(name="Rank", value=f"`#{position:,}`", inline=True)
    if percentile is not None:
        embed.add_field(
            name="Percentile", value=f"Top {100 - float(percentile):.2f}%", inline=True
        )
    if total_players is not None:
        embed.add_field(
            name="Total Players", value=f"`{int(total_players):,}`", inline=True
        )

    embed.set_footer(text="ArchMC Lifesteal • Official API")
    return embed
