import logging
import discord
import requests
import os
import io
import json
import asyncio
from datetime import datetime, time, timedelta
import zoneinfo
from collections import defaultdict
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

YEARLY_STATS_FILE = "yearly_stats.json"

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger('archie-bot')
load_dotenv()
bot = discord.Bot()

# Daily stats tracking
daily_stats = {
    "commands": defaultdict(int),  # command_name -> count
    "guilds": set(),  # unique guild ids
    "guild_usage": defaultdict(int),  # guild_id -> command count
    "guild_names": {},  # guild_id -> guild_name
    "start_time": datetime.now()
}

def reset_daily_stats():
    daily_stats["commands"] = defaultdict(int)
    daily_stats["guilds"] = set()
    daily_stats["guild_usage"] = defaultdict(int)
    daily_stats["guild_names"] = {}
    daily_stats["start_time"] = datetime.now()

# Yearly stats persistence
def load_yearly_stats():
    try:
        with open(YEARLY_STATS_FILE, "r") as f:
            data = json.load(f)
            return {
                "year": data.get("year", datetime.now().year),
                "commands": defaultdict(int, data.get("commands", {})),
                "total_commands": data.get("total_commands", 0),
                "guild_usage": defaultdict(int, data.get("guild_usage", {})),
                "guild_names": data.get("guild_names", {}),
            }
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "year": datetime.now().year,
            "commands": defaultdict(int),
            "total_commands": 0,
            "guild_usage": defaultdict(int),
            "guild_names": {},
        }

def save_yearly_stats():
    data = {
        "year": yearly_stats["year"],
        "commands": dict(yearly_stats["commands"]),
        "total_commands": yearly_stats["total_commands"],
        "guild_usage": dict(yearly_stats["guild_usage"]),
        "guild_names": yearly_stats["guild_names"],
    }
    with open(YEARLY_STATS_FILE, "w") as f:
        json.dump(data, f)

def reset_yearly_stats():
    yearly_stats["year"] = datetime.now().year
    yearly_stats["commands"] = defaultdict(int)
    yearly_stats["total_commands"] = 0
    yearly_stats["guild_usage"] = defaultdict(int)
    yearly_stats["guild_names"] = {}
    save_yearly_stats()

yearly_stats = load_yearly_stats()

def generate_stats_chart():
    commands = dict(daily_stats["commands"])
    if not commands:
        return None
    
    # Sort by usage count
    sorted_cmds = sorted(commands.items(), key=lambda x: x[1], reverse=True)
    names = [cmd for cmd, _ in sorted_cmds]
    counts = [count for _, count in sorted_cmds]
    
    # Create bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(names, counts, color='#5865F2')
    ax.set_xlabel('Usage Count')
    ax.set_title(f'Daily Command Usage - {daily_stats["start_time"].strftime("%Y-%m-%d")}')
    ax.invert_yaxis()
    
    # Add count labels
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                str(count), va='center', fontsize=10)
    
    plt.tight_layout()
    
    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close(fig)
    return buf

async def send_daily_recap():
    channel = bot.get_channel(STATS_CHANNEL)
    if not channel:
        return
    
    total_commands = sum(daily_stats["commands"].values())
    unique_guilds = len(daily_stats["guilds"])
    
    embed = discord.Embed(
        title="📈 Daily Stats Recap",
        description=f"Stats for **{daily_stats['start_time'].strftime('%Y-%m-%d')}**",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Total Commands", value=f"`{total_commands}`", inline=True)
    embed.add_field(name="Active Servers", value=f"`{unique_guilds}`", inline=True)
    
    # Top commands
    if daily_stats["commands"]:
        top_cmds = sorted(daily_stats["commands"].items(), key=lambda x: x[1], reverse=True)[:5]
        top_text = "\n".join([f"`/{cmd}` — {count}" for cmd, count in top_cmds])
        embed.add_field(name="Top Commands", value=top_text, inline=False)
    
    # Top servers
    if daily_stats["guild_usage"]:
        top_guilds = sorted(daily_stats["guild_usage"].items(), key=lambda x: x[1], reverse=True)[:5]
        top_guilds_text = "\n".join([
            f"**{daily_stats['guild_names'].get(gid, 'Unknown')}** — {count} commands"
            for gid, count in top_guilds
        ])
        embed.add_field(name="Top Servers", value=top_guilds_text, inline=False)
    
    embed.set_footer(text="Archie Daily Stats")
    
    # Generate chart
    chart = generate_stats_chart()
    if chart:
        file = discord.File(chart, filename="daily_stats.png")
        embed.set_image(url="attachment://daily_stats.png")
        await channel.send(embed=embed, file=file)
    else:
        await channel.send(embed=embed)
    
    reset_daily_stats()

def generate_yearly_wrapped_chart():
    commands = dict(yearly_stats["commands"])
    if not commands:
        return None
    
    sorted_cmds = sorted(commands.items(), key=lambda x: x[1], reverse=True)[:10]
    names = [cmd for cmd, _ in sorted_cmds]
    counts = [count for _, count in sorted_cmds]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    colors = plt.cm.viridis([i/len(names) for i in range(len(names))])
    bars = ax.barh(names, counts, color=colors)
    ax.set_xlabel('Usage Count', fontsize=14)
    ax.set_title(f'🎉 Archie Wrapped {yearly_stats["year"]} 🎉', fontsize=20, fontweight='bold')
    ax.invert_yaxis()
    
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + max(counts)*0.01, bar.get_y() + bar.get_height()/2, 
                f'{count:,}', va='center', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    plt.close(fig)
    return buf

async def send_yearly_wrapped():
    channel = bot.get_channel(STATS_CHANNEL)
    if not channel:
        return
    
    year = yearly_stats["year"]
    total_commands = yearly_stats["total_commands"]
    total_servers = len(yearly_stats["guild_usage"])
    
    embed = discord.Embed(
        title=f"🎉 Archie Wrapped {year} 🎉",
        description=f"Here's your year in review!",
        color=discord.Color.gold()
    )
    embed.add_field(name="📊 Total Commands", value=f"`{total_commands:,}`", inline=True)
    embed.add_field(name="🌐 Servers Reached", value=f"`{total_servers}`", inline=True)
    
    # Top commands
    if yearly_stats["commands"]:
        top_cmds = sorted(yearly_stats["commands"].items(), key=lambda x: x[1], reverse=True)[:5]
        top_text = "\n".join([f"**{i+1}.** `/{cmd}` — {count:,} uses" for i, (cmd, count) in enumerate(top_cmds)])
        embed.add_field(name="🏆 Top Commands", value=top_text, inline=False)
    
    # Top servers
    if yearly_stats["guild_usage"]:
        top_guilds = sorted(yearly_stats["guild_usage"].items(), key=lambda x: x[1], reverse=True)[:5]
        top_guilds_text = "\n".join([
            f"**{i+1}.** {yearly_stats['guild_names'].get(str(gid), 'Unknown')} — {count:,} commands"
            for i, (gid, count) in enumerate(top_guilds)
        ])
        embed.add_field(name="🏅 Top Servers", value=top_guilds_text, inline=False)
    
    embed.set_footer(text=f"Thank you for an amazing {year}! 💜")
    
    chart = generate_yearly_wrapped_chart()
    if chart:
        file = discord.File(chart, filename="wrapped.png")
        embed.set_image(url="attachment://wrapped.png")
        await channel.send(embed=embed, file=file)
    else:
        await channel.send(embed=embed)
    
    reset_yearly_stats()

async def daily_recap_loop():
    await bot.wait_until_ready()
    denmark_tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    while not bot.is_closed():
        now = datetime.now(denmark_tz)
        # Calculate seconds until midnight Danish time
        tomorrow = datetime(now.year, now.month, now.day, tzinfo=denmark_tz) + timedelta(days=1)
        seconds_until_midnight = (tomorrow - now).total_seconds()
        await asyncio.sleep(seconds_until_midnight)
        
        # Check if it's New Year (Jan 1st) - send wrapped for previous year
        now = datetime.now(denmark_tz)
        if now.month == 1 and now.day == 1:
            await send_yearly_wrapped()
        
        await send_daily_recap()

@bot.slash_command(
    name="balance",
    description="Show a player's balance for a selected gamemode",
    options=[
        discord.Option(
            str,
            "Select the gamemode",
            choices=["lifesteal", "survival", "bedwars", "kitpvp", "skywars"],
            required=True,
            name="gamemode"
        ),
        discord.Option(
            str,
            "Minecraft username",
            required=True,
            name="username"
        )
    ]
)
async def balance(ctx: discord.ApplicationContext, gamemode: str, username: str):
    await ctx.defer()
    try:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        username_lower = username.lower()
        # Map gamemode to balance key in balances dict
        type_map = {
            "lifesteal": "lifesteal-coins",
            "survival": "gems",
            "bedwars": "bedwars-coins",
            "kitpvp": "kitpvp-coins",
            "skywars": "skywars-coins"
        }
        bal_type = type_map.get(gamemode)
        if not bal_type:
            await ctx.respond("Invalid gamemode selected.")
            return
        url = f"https://api.arch.mc/v1/economy/player/username/{username_lower}"
        headers = {"X-API-KEY": API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            balances = data.get("balances", {})
            if not balances:
                await ctx.respond(f"No balance data found for {username}. The player may not have played any supported gamemode yet.")
                return
            if bal_type in balances:
                balance = balances[bal_type]
                embed = discord.Embed(
                    title=f"💰 {gamemode.capitalize()} Balance for {username}",
                    description=f"**{balance:,}**",
                    color=discord.Color.gold()
                )
                embed.set_footer(text=f"ArchMC {gamemode.capitalize()} • Official API")
                await ctx.respond(embed=embed)
            else:
                # Show all available balances for the player
                bal_lines = [f"**{k.replace('-', ' ').title()}**: `{v:,}`" for k, v in balances.items()]
                embed = discord.Embed(
                    title=f"💰 All Balances for {username}",
                    description="\n".join(bal_lines),
                    color=discord.Color.gold()
                )
                embed.set_footer(text="ArchMC Economy • Official API")
                await ctx.respond(
                    content=f"No {gamemode} balance found for {username}. Showing all available balances:",
                    embed=embed
                )
        elif response.status_code == 404:
            await ctx.respond(f"No balance profile found for **{username}**. The player may not exist or has never played on ArchMC.")
        else:
            await ctx.respond(f"Failed to fetch balance for {username} in {gamemode}. (Status code: {response.status_code})")
    except Exception as e:
        await ctx.respond(f"Failed to fetch balance: {e}")

# /dueltop - Top players for a duel stat (ELO, wins, etc.)
@bot.slash_command(
    name="dueltop",
    description="Show the top players for a selected Duel stat",
    options=[
        discord.Option(
            str,
            "Select the duel stat",
            choices=[
                "elo:nodebuff:ranked:lifetime",
                "elo:sumo:ranked:lifetime",
                "elo:bridge:ranked:lifetime",
                "wins:nodebuff:ranked:lifetime",
                "wins:sumo:ranked:lifetime",
                "wins:bridge:ranked:lifetime"
            ],
            required=True,
            name="statid"
        )
    ]
)
async def dueltop(ctx: discord.ApplicationContext, statid: str):
    await ctx.defer()
    try:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        url = f"https://api.arch.mc/v1/leaderboards/{statid}?page=0&size=10"
        headers = {"X-API-KEY": API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            entries = data.get("entries") or data.get("leaderboard") or []
            if isinstance(entries, list) and entries:
                leaderboard_lines = [
                    f"**#{entry.get('position', i+1)}** {entry.get('username', 'Unknown')} — `{entry.get('value', 0)}`"
                    for i, entry in enumerate(entries)
                ]
                leaderboard_text = "\n".join(leaderboard_lines)
                embed = discord.Embed(
                    title=f"🥊 Duel Top: {statid}",
                    description=leaderboard_text,
                    color=discord.Color.blue()
                )
                embed.set_footer(text="ArchMC Duels • Official API")
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No duel leaderboard data found.")
        else:
            await ctx.respond(f"Failed to fetch duel leaderboard. Status code: {response.status_code}")
    except Exception as e:
        await ctx.respond(f"Failed to fetch duel leaderboard: {e}")

# /duelstats - All duel stats for a username

# --- Pagination for /duelstats ---
from discord.ui import View, Button

def build_duelstats_embed(data, username, mode_stats, mode_labels, mode_keys, page, page_size):
    # Format like /lifestats: one field per stat, all inline, with emoji and stat name
    modes_per_page = 4
    start = page * modes_per_page
    end = start + modes_per_page
    shown_modes = mode_keys[start:end]
    embed = discord.Embed(
        title=f"Archie — 🥊 Duel Stats for {data.get('username', username)}",
        color=discord.Color.purple(),
        description=f"Page {page+1} of {((len(mode_keys)-1)//modes_per_page)+1}"
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1454187186651009116/3e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e.png?size=128")
    for mode in shown_modes:
        emoji, label = mode_labels.get(mode, ("❓", mode.capitalize()))
        # ELO fields
        for context, v in mode_stats[mode]["ELO"]:
            value = v.get("value", 0) if isinstance(v, dict) and "value" in v else v
            context_str = f" ({context})" if context else ""
            stat_name = f"{emoji} {label} ELO{context_str}" if context_str else f"{emoji} {label} ELO"
            embed.add_field(name=stat_name, value=f"`{value}`", inline=True)
        # Wins fields
        for context, v in mode_stats[mode]["WINS"]:
            value = v.get("value", 0) if isinstance(v, dict) and "value" in v else v
            context_str = f" ({context})" if context else ""
            stat_name = f"{emoji} {label} Wins{context_str}" if context_str else f"{emoji} {label} Wins"
            embed.add_field(name=stat_name, value=f"`{value}`", inline=True)
        # Other fields
        for stat_type in mode_stats[mode]:
            if stat_type in ("ELO", "WINS"): continue
            for context, v in mode_stats[mode][stat_type]:
                value = v.get("value", 0) if isinstance(v, dict) and "value" in v else v
                context_str = f" ({context})" if context else ""
                stat_name = f"{emoji} {label} {stat_type}{context_str}" if context_str else f"{emoji} {label} {stat_type}"
                embed.add_field(name=stat_name, value=f"`{value}`", inline=True)
    embed.set_footer(text="Archie • ArchMC Duels • Official API")
    return embed

class DuelStatsView(View):
    def __init__(self, data, username, mode_stats, mode_labels, mode_keys, page):
        super().__init__(timeout=60)
        self.data = data
        self.username = username
        self.mode_stats = mode_stats
        self.mode_labels = mode_labels
        self.mode_keys = mode_keys
        self.page = page
        self.modes_per_page = 4
        self.max_page = (len(mode_keys) - 1) // self.modes_per_page
        # Add persistent buttons with callbacks
        if self.page > 0:
            self.add_item(self.PrevButton(self))
        if self.page < self.max_page:
            self.add_item(self.NextButton(self))

    class PrevButton(Button):
        def __init__(self, parent):
            super().__init__(label="Prev", style=discord.ButtonStyle.primary)
            self.parent = parent
        async def callback(self, interaction: discord.Interaction):
            if self.parent.page > 0:
                self.parent.page -= 1
                embed = build_duelstats_embed(
                    self.parent.data, self.parent.username, self.parent.mode_stats, self.parent.mode_labels, self.parent.mode_keys, self.parent.page, self.parent.modes_per_page
                )
                # Rebuild view for new page
                new_view = DuelStatsView(self.parent.data, self.parent.username, self.parent.mode_stats, self.parent.mode_labels, self.parent.mode_keys, self.parent.page)
                await interaction.response.edit_message(embed=embed, view=new_view)

    class NextButton(Button):
        def __init__(self, parent):
            super().__init__(label="Next", style=discord.ButtonStyle.primary)
            self.parent = parent
        async def callback(self, interaction: discord.Interaction):
            if self.parent.page < self.parent.max_page:
                self.parent.page += 1
                embed = build_duelstats_embed(
                    self.parent.data, self.parent.username, self.parent.mode_stats, self.parent.mode_labels, self.parent.mode_keys, self.parent.page, self.parent.modes_per_page
                )
                # Rebuild view for new page
                new_view = DuelStatsView(self.parent.data, self.parent.username, self.parent.mode_stats, self.parent.mode_labels, self.parent.mode_keys, self.parent.page)
                await interaction.response.edit_message(embed=embed, view=new_view)

@bot.slash_command(
    name="duelstats",
    description="Show all duel stats for a player",
    options=[
        discord.Option(
            str,
            "Minecraft username",
            required=True,
            name="username"
        )
    ]
)
async def duelstats(ctx: discord.ApplicationContext, username: str):
    await ctx.defer()
    import traceback
    try:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        url = f"https://api.arch.mc/v1/players/username/{username.lower()}/statistics"
        headers = {"X-API-KEY": API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            statistics = data.get("statistics", {})
            duel_stats = {k: v for k, v in statistics.items() if k.startswith("elo:") or k.startswith("wins:")}
            logger.info(f"[duelstats] username={username} duel_stats_keys={list(duel_stats.keys())}")
            if duel_stats:
                try:
                    from collections import defaultdict
                    mode_labels = {
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
                                mode_stats[mode][stat_type].append((context, v))
                        else:
                            mode_stats["other"]["OTHER"].append((k, v))
                    mode_keys = sorted(mode_stats.keys())
                    page = 0
                    embed = build_duelstats_embed(data, username, mode_stats, mode_labels, mode_keys, page, 4)
                    view = DuelStatsView(data, username, mode_stats, mode_labels, mode_keys, page)
                    await ctx.respond(embed=embed, view=view)
                except Exception as group_exc:
                    logger.error(f"[duelstats] Grouping error for {username}: {group_exc}\n{traceback.format_exc()}")
                    await ctx.respond("Failed to format duel stats.")
            else:
                await ctx.respond("No duel stats found for that player.")
        else:
            await ctx.respond(f"Failed to fetch duel stats. Status code: {response.status_code}")
    except Exception as e:
        logger.error(f"[duelstats] Exception for {username}: {e}\n{traceback.format_exc()}")
        await ctx.respond(f"Failed to fetch duel stats: {e}")


# Load channel IDs from environment
GUILD_JOIN_CHANNEL = int(os.getenv("GUILD_JOIN_CHANNEL", 0))
GUILD_LEAVE_CHANNEL = int(os.getenv("GUILD_LEAVE_CHANNEL", 0))
# Hardcode BOT_ERRORS_CHANNEL as requested
BOT_ERRORS_CHANNEL = 1454137711710703785
STATS_CHANNEL = 1465102978644971858
BOT_STATUS_CHANNEL = 1454137711140147332

@bot.slash_command(
    name="lifetop",
    description="Show the top players for a selected Lifesteal stat",
    options=[
        discord.Option(
            str,
            "Select the statistic",
            choices=["kills", "deaths", "killstreak", "killDeathRatio", "blocksMined", "blocksWalked", "blocksPlaced"],
            required=True,
            name="stat"
        )
    ]
)
async def lifetop(ctx: discord.ApplicationContext, stat: str):
    await ctx.defer()
    try:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        client = PIGDIClient(API_KEY)
        leaderboard = client.get_ugc_leaderboard("trojan", stat)
        if leaderboard and "entries" in leaderboard:
            leaderboard_lines = [
                f"**#{entry.get('position', i+1)}** {entry.get('username', 'Unknown')} — `{entry.get('value', 0)}`"
                for i, entry in enumerate(leaderboard["entries"])
            ]
            leaderboard_text = "\n".join(leaderboard_lines)
            embed = discord.Embed(
                title=f"🏆 Lifesteal Top {stat.capitalize()}",
                description=leaderboard_text,
                color=discord.Color.red()
            )
            embed.set_footer(text="ArchMC Lifesteal • Official API")
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("No leaderboard data found.")
    except Exception as e:
        await ctx.respond(f"Failed to fetch leaderboard: {e}")

# /lifestats - All Lifesteal stats for a username


@bot.slash_command(
    name="lifestats",
    description="Show all Lifesteal stats and profile for a player",
    options=[
        discord.Option(
            str,
            "Minecraft username",
            required=True,
            name="username"
        )
    ]
)
async def lifestats(ctx: discord.ApplicationContext, username: str):
    await ctx.defer()
    try:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        client = PIGDIClient(API_KEY)
        username_lower = username.lower()
        # Get stats
        stats = client._request("GET", f"/v1/ugc/trojan/players/username/{username_lower}/statistics")
        # Get profile
        profile = client._request("GET", f"/v1/ugc/trojan/players/username/{username_lower}/profile")
        if stats and isinstance(stats, dict):
            username_disp = stats.get("username", username)
            statistics = stats.get("statistics", {})
            stat_emojis = {
                "kills": "⚔️",
                "deaths": "💀",
                "killstreak": "🔥",
                "killDeathRatio": "📊",
                "blocksMined": "⛏️",
                "blocksWalked": "🚶",
                "blocksPlaced": "🧱"
            }
            embed = discord.Embed(
                title=f"📊 Lifesteal Stats for {username_disp}",
                color=discord.Color.red()
            )
            # Card-style: one field per stat, all inline
            for k, v in statistics.items():
                emoji = stat_emojis.get(k, "📈")
                name = f"{emoji} {k.capitalize()}"
                value_lines = []
                if isinstance(v, dict) and "value" in v:
                    value_lines.append(f"Value: `{v.get('value', 0)}`")
                    if v.get('position') is not None:
                        value_lines.append(f"Rank: `#{v.get('position'):,}`")
                    if v.get('percentile') is not None:
                        value_lines.append(f"Percentile: Top {100 - float(v.get('percentile')):.2f}%")
                else:
                    value_lines.append(f"Value: `{v}`")
                embed.add_field(name=name, value="\n".join(value_lines), inline=True)
            # Add profile info if available
            if profile and isinstance(profile, dict):
                profile_lines = []
                for k, v in profile.items():
                    if k in ("username", "uuid") or isinstance(v, (dict, list)):
                        continue
                    label = k.replace('_', ' ').capitalize()
                    # Special formatting for totalPlaytimeSeconds
                    if k.lower() == "totalplaytimeseconds" and isinstance(v, (int, float)):
                        hours = int(v // 1000 // 3600)
                        days = int(hours // 24)
                        label = "Total Playtime"
                        value_str = f"{hours} hours ({days} days)"
                    else:
                        value_str = v
                    profile_lines.append(f"**{label}**: `{value_str}`")
                if profile_lines:
                    embed.add_field(name="Profile Info", value="\n".join(profile_lines), inline=False)
            embed.set_footer(text="ArchMC Lifesteal • Official API")
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("No stats found for that player.")
    except Exception as e:
        await ctx.respond(f"Failed to fetch stats: {e}")

# /lifestat - Specific Lifesteal stat for a username

# Utility: Format a stat dict as a Discord embed
def stat_to_embed(stat: dict, stat_name: str, username: str) -> discord.Embed:
    stat_emojis = {
        "kills": "⚔️",
        "deaths": "💀",
        "killstreak": "🔥",
        "killDeathRatio": "📊",
        "blocksMined": "⛏️",
        "blocksWalked": "🚶",
        "blocksPlaced": "🧱"
    }
    emoji = stat_emojis.get(stat_name, "📈")
    value = stat.get("value", stat.get("statValue", 0))
    position = stat.get("position")
    percentile = stat.get("percentile")
    total_players = stat.get("totalPlayers")
    embed = discord.Embed(
        title=f"{emoji} {stat_name.capitalize()} — {username}",
        description=f"**{value}**",
        color=discord.Color.red()
    )
    if position is not None:
        embed.add_field(name="Rank", value=f"`#{position:,}`", inline=True)
    if percentile is not None:
        embed.add_field(name="Percentile", value=f"Top {100 - float(percentile):.2f}%", inline=True)
    if total_players is not None:
        embed.add_field(name="Total Players", value=f"`{int(total_players):,}`", inline=True)
    embed.set_footer(text="ArchMC Lifesteal • Official API")
    return embed

@bot.slash_command(
    name="lifestat",
    description="Show a specific Lifesteal stat for a player",
    options=[
        discord.Option(
            str,
            "Minecraft username",
            required=True,
            name="username"
        ),
        discord.Option(
            str,
            "Select the statistic",
            choices=["kills", "deaths", "killstreak", "killDeathRatio", "blocksMined", "blocksWalked", "blocksPlaced"],
            required=True,
            name="stat"
        )
    ]
)
async def lifestat(ctx: discord.ApplicationContext, username: str, stat: str):
    await ctx.defer()
    try:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        client = PIGDIClient(API_KEY)
        username_lower = username.lower()
        # Try to get detailed stat info (with rank/percentile)
        stat_info = client._request("GET", f"/v1/ugc/trojan/players/username/{username_lower}/statistics/{stat}")
        if stat_info and isinstance(stat_info, dict) and "value" in stat_info:
            embed = stat_to_embed(stat_info, stat, username)
            await ctx.respond(embed=embed)
        else:
            # fallback: try to get value from summary stats
            stats = client.get_ugc_player_stats_by_username("trojan", username_lower)
            stat_val = stats["statistics"].get(stat) if stats and "statistics" in stats and stat in stats["statistics"] else None
            if stat_val is not None:
                # If fallback is just a value, wrap in dict
                if not isinstance(stat_val, dict):
                    stat_val = {"value": stat_val}
                embed = stat_to_embed(stat_val, stat, username)
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No data found for that player/stat.")
    except Exception as e:
        await ctx.respond(f"Failed to fetch stat: {e}")


# /clantop - Top Clans Leaderboard
@bot.slash_command(name="clantop", description="Show the top clans from ArchMC")
async def clantop(ctx: discord.ApplicationContext):
    await ctx.defer()
    try:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        url = "https://api.arch.mc/v1/ugc/trojan/clans?page=0&size=10"
        headers = {"X-API-KEY": API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            clans = data.get("clans") or data.get("entries") or data.get("leaderboard") or []
            if isinstance(clans, list) and clans:
                leaderboard_lines = []
                for i, clan in enumerate(clans):
                    name = clan.get("displayName") or clan.get("name") or clan.get("clanName") or "Unknown"
                    level = clan.get("level", 0)
                    if isinstance(level, float):
                        level = int(level)
                    leader = clan.get("leaderUsername", "Unknown")
                    members = clan.get("memberCount", 0)
                    leaderboard_lines.append(f"**#{i+1} {name}** — Level {level} | Leader: {leader} | Members: {members}")
                leaderboard_text = "\n".join(leaderboard_lines)
                embed = discord.Embed(
                    title="🏅 Top Clans",
                    description=leaderboard_text,
                    color=discord.Color.gold()
                )
                embed.set_footer(text="ArchMC Clans • Official API")
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No clan leaderboard data found.")
        else:
            await ctx.respond(f"Failed to fetch clan leaderboard. Status code: {response.status_code}")
    except Exception as e:
        await ctx.respond(f"Failed to fetch clan leaderboard: {e}")


# Move sync_commands to after all commands are defined

@bot.event
async def on_ready():
    logger.info(f"{bot.user} is ready and online! Registering commands...")
    # Force sync and block until done
    await bot.sync_commands()
    logger.info(f"{bot.user} commands synced!")
    # Start daily recap loop
    bot.loop.create_task(daily_recap_loop())
    # Send online status
    try:
        status_channel = bot.get_channel(BOT_STATUS_CHANNEL) or await bot.fetch_channel(BOT_STATUS_CHANNEL)
        if status_channel:
            await status_channel.send("🟢 **Archie is now online!**")
    except Exception as e:
        logger.error(f"Failed to send online status: {e}")
    # Notify in Discord that commands are synced
    try:
        channel = bot.get_channel(1454137711710703783)
        if channel:
            await channel.send("✅ Archie slash commands are now fully synced and ready to use!")
            guilds = list(bot.guilds)
            if guilds:
                guild_list = "\n".join([f"- {g.name} (ID: {g.id})" for g in guilds])
                msg = f"Archie is currently in the following servers ({len(guilds)}):\n{guild_list}"
            else:
                msg = "Archie is not in any servers."
            await channel.send(msg)
        else:
            logger.warning("Could not find the specified channel to send guild list.")
    except Exception as e:
        logger.error(f"Failed to send guild list: {e}")

# Track command usage for daily stats
@bot.event
async def on_application_command(ctx):
    logger.info(f"/{ctx.command.name} used by {ctx.author} in {getattr(ctx.guild, 'name', 'DM')}")
    
    # Track daily stats
    daily_stats["commands"][ctx.command.name] += 1
    if ctx.guild:
        daily_stats["guilds"].add(ctx.guild.id)
        daily_stats["guild_usage"][ctx.guild.id] += 1
        daily_stats["guild_names"][ctx.guild.id] = ctx.guild.name
    
    # Track yearly stats
    yearly_stats["commands"][ctx.command.name] += 1
    yearly_stats["total_commands"] += 1
    if ctx.guild:
        yearly_stats["guild_usage"][str(ctx.guild.id)] += 1
        yearly_stats["guild_names"][str(ctx.guild.id)] = ctx.guild.name
    save_yearly_stats()


@bot.event
async def on_guild_join(guild):
    channel = bot.get_channel(GUILD_JOIN_CHANNEL)
    if channel:
        await channel.send(f"✅ Joined guild: **{guild.name}** (ID: {guild.id})")

@bot.event
async def on_guild_remove(guild):
    channel = bot.get_channel(GUILD_LEAVE_CHANNEL)
    if channel:
        await channel.send(f"❌ Left guild: **{guild.name}** (ID: {guild.id})")

@bot.event
async def on_error(event, *args, **kwargs):
    import traceback
    logger.error(f"Error in event {event}:\n{traceback.format_exc()}")
    channel = bot.get_channel(BOT_ERRORS_CHANNEL)
    if channel:
        error_msg = f"⚠️ Error in event `{event}`:\n```py\n{traceback.format_exc()}```"
        await channel.send(error_msg[:2000])


# /playtime - Playtime leaderboard for Lifesteal and Survival
@bot.slash_command(
    name="playtime",
    description="Show the playtime leaderboard for a selected mode",
    options=[
        discord.Option(
            str,
            "Select the server mode",
            choices=["lifesteal", "survival"],
            required=True,
            name="mode"
        )
    ]
)
async def playtime(ctx: discord.ApplicationContext, mode: str):
    await ctx.defer()
    try:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        client = PIGDIClient(API_KEY)
        # Map mode to gamemode
        gamemode = "trojan" if mode == "lifesteal" else "spartan"
        leaderboard = client._request("GET", f"/v1/ugc/{gamemode}/leaderboard/playtime?page=0&size=10")
        entries = leaderboard.get("entries") or leaderboard.get("players") or leaderboard.get("leaderboard") or []
        if isinstance(entries, list) and entries:
            leaderboard_lines = []
            for i, entry in enumerate(entries):
                username = entry.get("username") or entry.get("name") or "Unknown"
                playtime_ms = entry.get("playtimeSeconds") or 0
                playtime_hours = int(playtime_ms // 1000 // 3600)
                leaderboard_lines.append(f"**#{entry.get('position', i+1)}** {username} — `{playtime_hours} hours`")
            leaderboard_text = "\n".join(leaderboard_lines)
            color = discord.Color.red() if mode == "lifesteal" else discord.Color.green()
            embed = discord.Embed(
                title=f"⏱️ {mode.capitalize()} Playtime Top",
                description=leaderboard_text,
                color=color
            )
            embed.set_footer(text=f"ArchMC {mode.capitalize()} • Official API")
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("No leaderboard data found.")
    except Exception as e:
        await ctx.respond(f"Failed to fetch playtime leaderboard: {e}")


# /baltop command for various leaderboards

# /baltop - Economy leaderboard for various currencies
@bot.slash_command(
    name="baltop",
    description="Show the baltop leaderboard for a selected type",
    options=[
        discord.Option(
            str,
            "Select the baltop type",
            choices=[
                "lifesteal-coins",
                "bedwars-coins",
                "kitpvp-coins",
                "gems",
                "bedwars-experience",
                "skywars-coins",
                "skywars-experience"
            ],
            required=True,
            name="type"
        )
    ]
)
async def baltop(ctx: discord.ApplicationContext, type: str):
    await ctx.defer()
    try:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        url = f"https://api.arch.mc/v1/economy/baltop/{type}"
        headers = {"X-API-KEY": API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            entries = data.get("entries") or []
            if isinstance(entries, list) and entries:
                leaderboard_lines = [
                    f"**#{entry.get('position', i+1)}** {entry.get('username', 'Unknown')} — `{entry.get('balance', 0)}`"
                    for i, entry in enumerate(entries)
                ]
                leaderboard_text = "\n".join(leaderboard_lines)
                embed = discord.Embed(
                    title=f"🏦 Baltop Leaderboard: {type.replace('-', ' ').title()}",
                    description=leaderboard_text,
                    color=discord.Color.gold()
                )
                embed.set_footer(text="ArchMC Baltop • Official API")
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No baltop data found for that type.")
        else:
            await ctx.respond(f"Failed to fetch baltop leaderboard. Status code: {response.status_code}")
    except Exception as e:
        await ctx.respond(f"Failed to fetch baltop leaderboard: {e}")

@bot.slash_command(name="invite", description="Get the invite link for Archie")
async def invite(ctx: discord.ApplicationContext):
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
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="Thank you for supporting Archie!")
    await ctx.respond(embed=embed)

@bot.slash_command(name="help", description="Show help for Archie commands")
async def help(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title="Archie Help",
        description="**Here are all available commands:**",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="/playtime",
        value="⏱️ Show the playtime leaderboard for Lifesteal or Survival.",
        inline=False
    )
    embed.add_field(
        name="/lifetop",
        value="🏆 Show the top players for a selected Lifesteal stat.",
        inline=False
    )
    embed.add_field(
        name="/lifestats",
        value="📊 Show all Lifesteal stats and profile for a player (card style).",
        inline=False
    )
    embed.add_field(
        name="/lifestat",
        value="📈 Show a specific Lifesteal stat for a player, with value, rank, and percentile.",
        inline=False
    )
    embed.add_field(
        name="/dueltop",
        value="🥊 Show the top players for a selected Duel stat (ELO or Wins).",
        inline=False
    )
    embed.add_field(
        name="/duelstats",
        value="🎴 Show all Duel stats for a player, grouped and paginated (card style).",
        inline=False
    )
    embed.add_field(
        name="/balance",
        value="💰 Show a player's balance for a selected gamemode.",
        inline=False
    )
    embed.add_field(
        name="/baltop",
        value="🏦 Show the baltop leaderboard for a selected currency or experience type.",
        inline=False
    )
    embed.add_field(
        name="/clantop",
        value="🏅 Show the top clans from ArchMC.",
        inline=False
    )
    embed.add_field(
        name="/invite",
        value="➕ Get the invite link for Archie and the support server.",
        inline=False
    )
    embed.set_footer(text="More commands and features coming soon! | Archie by ArchMC")
    await ctx.respond(embed=embed)


class PIGDIClient:
    BASE_URL = "https://api.arch.mc"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"X-API-KEY": self.api_key})

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.BASE_URL}{path}"
        resp = self.session.request(method, url, **kwargs)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            print(f"HTTP error: {e} - {resp.text}")
            return None
        if resp.headers.get("Content-Type", "").startswith("application/json"):
            return resp.json()
        return resp.text

    # Example: Get all statistics for a player by username (UGC)
    def get_ugc_player_stats_by_username(self, gamemode: str, username: str) -> Optional[Dict]:
        path = f"/v1/ugc/{gamemode}/players/username/{username}/statistics"
        return self._request("GET", path)

    # Example: Get leaderboard for a statistic (UGC)
    def get_ugc_leaderboard(self, gamemode: str, stat_type: str, page: int = 0, size: int = 10) -> Optional[Dict]:
        path = f"/v1/ugc/{gamemode}/leaderboard/{stat_type}?page={page}&size={size}"
        return self._request("GET", path)

    # Example: Get all available statistic IDs
    def list_statistics(self) -> Optional[Dict]:
        path = "/v1/statistics"
        return self._request("GET", path)

# Example usage
if __name__ == "__main__":
    bot.run(os.getenv('TOKEN')) # run the bot with the token
