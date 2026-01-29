import logging
import discord
import aiohttp
import os
import io
import json
import asyncio
import re
import filelock
from datetime import datetime, time, timedelta
import zoneinfo
from collections import defaultdict
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

# === SECURITY: Rate limiting / cooldowns ===
from discord.ext import commands
user_cooldowns: Dict[int, datetime] = {}
COOLDOWN_SECONDS = 3

def check_cooldown(user_id: int) -> bool:
    """Returns True if user is on cooldown (should be blocked)"""
    now = datetime.now()
    if user_id in user_cooldowns:
        elapsed = (now - user_cooldowns[user_id]).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            return True
    user_cooldowns[user_id] = now
    return False

# === SECURITY: Username sanitization ===
USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_]{1,16}$')

# === SECURITY: Blocked words/patterns in usernames (case-insensitive) ===
# Filters out usernames containing slurs, racist terms, or other offensive content
BLOCKED_PATTERNS = {
    "nigger", "nigga", "n1gger", "n1gga", "nigg3r", "nigg4",
    "faggot", "f4ggot", "fag",
    "retard", "r3tard",
    "kike", "chink", "spic", "wetback", "beaner",
    "tranny", "trannie",
    # Add more blocked patterns here
}

def is_username_blocked(username: str) -> bool:
    """Check if a username contains blocked/offensive terms."""
    lower = username.lower()
    return any(pattern in lower for pattern in BLOCKED_PATTERNS)

def sanitize_username(username: str) -> Optional[str]:
    """Validate and sanitize Minecraft username. Returns None if invalid."""
    username = username.strip()[:16]
    if USERNAME_REGEX.match(username):
        return username
    return None

# === SECURITY: Safe JSON file operations with file locking ===
def safe_json_load(filepath: str, default: dict) -> dict:
    """Safely load JSON with file locking to prevent corruption."""
    lock = filelock.FileLock(f"{filepath}.lock", timeout=5)
    try:
        with lock:
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    return json.load(f)
    except (json.JSONDecodeError, filelock.Timeout, Exception) as e:
        logging.getLogger('archie-bot').error(f"Failed to load {filepath}: {e}")
    return default

def safe_json_save(filepath: str, data: dict) -> bool:
    """Safely save JSON with file locking and atomic write."""
    lock = filelock.FileLock(f"{filepath}.lock", timeout=5)
    try:
        with lock:
            tmp_path = f"{filepath}.tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, filepath)
            return True
    except (filelock.Timeout, Exception) as e:
        logging.getLogger('archie-bot').error(f"Failed to save {filepath}: {e}")
    return False

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.png")
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "MinecraftRegular.otf")
STEVE_HEAD_URL = "https://mc-heads.net/avatar/MHF_Steve/80"

async def fetch_player_head(uuid: str) -> Optional[bytes]:
    """Async fetch player head with timeout protection."""
    head_urls = [f"https://mc-heads.net/avatar/{uuid}/80", STEVE_HEAD_URL]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        for url in head_urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if len(data) > 100:
                            return data
            except:
                continue
    return None

def generate_lifestats_card(username: str, uuid: str, statistics: dict, profile: dict, head_data: Optional[bytes] = None) -> io.BytesIO:
    from PIL import ImageFilter
    
    # Colors (Minecraft style)
    GOLD = "#FFAA00"
    GREEN = "#55FF55"
    AQUA = "#55FFFF"
    PINK = "#FF55FF"
    WHITE = "#FFFFFF"
    GRAY = "#AAAAAA"
    BG_COLOR = (20, 20, 20, 200)
    BORDER_COLOR = (100, 100, 100, 255)
    
    card_width, card_height = 800, 520
    card = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    
    draw.rounded_rectangle([0, 0, card_width-1, card_height-1], radius=12, fill=BG_COLOR, outline=BORDER_COLOR, width=2)
    
    # Load Minecraft font - larger sizes for readability
    try:
        font_large = ImageFont.truetype(FONT_PATH, 40)
        font_medium = ImageFont.truetype(FONT_PATH, 32)
        font_small = ImageFont.truetype(FONT_PATH, 26)
        font_tiny = ImageFont.truetype(FONT_PATH, 20)
    except:
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large
        font_tiny = font_large
    
    # Use pre-fetched head data or create placeholder
    skin_img = None
    if head_data:
        try:
            skin_img = Image.open(io.BytesIO(head_data)).convert("RGBA")
            if skin_img.size[0] <= 0 or skin_img.size[1] <= 0:
                skin_img = None
        except:
            skin_img = None
    
    # Final fallback - create a Steve-colored placeholder
    if skin_img is None:
        skin_img = Image.new("RGBA", (80, 80), (139, 90, 43, 255))
    
    def mc_text(x, y, text, font, color):
        shadow = tuple(max(0, int(int(color.lstrip('#')[i:i+2], 16) * 0.3)) for i in (0, 2, 4))
        draw.text((x+2, y+2), text, font=font, fill=shadow)
        draw.text((x, y), text, font=font, fill=color)
    
    def mc_text_centered(x, y, text, font, color):
        bbox = draw.textbbox((0, 0), text, font=font)
        mc_text(x - (bbox[2] - bbox[0]) // 2, y, text, font, color)
    
    def get_stat_value(stat_name):
        stat = statistics.get(stat_name, {})
        return stat.get("value", 0) if isinstance(stat, dict) else (stat or 0)
    
    def get_stat_rank(stat_name):
        stat = statistics.get(stat_name, {})
        return stat.get("position") if isinstance(stat, dict) else None
    
    def format_number(n):
        if isinstance(n, float): return f"{n:.2f}"
        if isinstance(n, int):
            if n >= 1000000: return f"{n/1000000:.2f}M"
            return f"{n:,}"
        return str(n)
    
    # Header
    draw.line([(20, 100), (card_width - 20, 100)], fill=BORDER_COLOR, width=1)
    skin_img = skin_img.resize((80, 80), Image.Resampling.LANCZOS)
    card.paste(skin_img, (25, 12), skin_img)
    draw.rectangle([24, 11, 106, 93], outline=BORDER_COLOR, width=2)
    mc_text(120, 25, username, font_large, WHITE)
    mc_text(120, 60, "Lifesteal Player", font_small, GREEN)
    playtime_ms = profile.get("totalPlaytimeSeconds", 0) if profile else 0
    hours = int(playtime_ms // 1000 // 3600) if playtime_ms else 0
    mc_text(card_width - 200, 25, "Playtime", font_tiny, GRAY)
    mc_text(card_width - 200, 45, f"{hours//24}d {hours%24}h", font_medium, AQUA)
    
    # Row 1 - Combat stats
    draw.line([(20, 180), (card_width - 20, 180)], fill=BORDER_COLOR, width=1)
    col4 = (card_width - 40) // 4
    for i, (label, key) in enumerate([("Kills", "kills"), ("Deaths", "deaths"), ("K/D Ratio", "killDeathRatio"), ("Best Streak", "killstreak")]):
        mc_text_centered(20 + col4*i + col4//2, 115, label, font_small, GOLD)
        mc_text_centered(20 + col4*i + col4//2, 140, format_number(get_stat_value(key)), font_large, GOLD)
    for i in range(1, 4): draw.line([(20 + col4*i, 105), (20 + col4*i, 175)], fill=BORDER_COLOR, width=1)
    
    # Row 2 - Activity stats
    draw.line([(20, 260), (card_width - 20, 260)], fill=BORDER_COLOR, width=1)
    col3 = (card_width - 40) // 3
    for i, (label, key) in enumerate([("Blocks Mined", "blocksMined"), ("Blocks Walked", "blocksWalked"), ("Blocks Placed", "blocksPlaced")]):
        mc_text_centered(20 + col3*i + col3//2, 195, label, font_small, GREEN)
        mc_text_centered(20 + col3*i + col3//2, 220, format_number(get_stat_value(key)), font_large, GREEN)
    for i in range(1, 3): draw.line([(20 + col3*i, 185), (20 + col3*i, 255)], fill=BORDER_COLOR, width=1)
    
    # Row 3 - Combat ranks
    draw.line([(20, 340), (card_width - 20, 340)], fill=BORDER_COLOR, width=1)
    for i, (label, key) in enumerate([("Kills Rank", "kills"), ("Deaths Rank", "deaths"), ("K/D Rank", "killDeathRatio"), ("Streak Rank", "killstreak")]):
        rank = get_stat_rank(key)
        mc_text_centered(20 + col4*i + col4//2, 275, label, font_small, PINK)
        mc_text_centered(20 + col4*i + col4//2, 300, f"#{rank:,}" if rank else "N/A", font_large, PINK)
    for i in range(1, 4): draw.line([(20 + col4*i, 265), (20 + col4*i, 335)], fill=BORDER_COLOR, width=1)
    
    # Row 4 - Activity ranks
    draw.line([(20, 420), (card_width - 20, 420)], fill=BORDER_COLOR, width=1)
    for i, (label, key) in enumerate([("Mined Rank", "blocksMined"), ("Walked Rank", "blocksWalked"), ("Placed Rank", "blocksPlaced")]):
        rank = get_stat_rank(key)
        mc_text_centered(20 + col3*i + col3//2, 355, label, font_small, AQUA)
        mc_text_centered(20 + col3*i + col3//2, 380, f"#{rank:,}" if rank else "N/A", font_large, AQUA)
    for i in range(1, 3): draw.line([(20 + col3*i, 345), (20 + col3*i, 415)], fill=BORDER_COLOR, width=1)
    
    # Footer
    mc_text_centered(card_width // 2, 440, "ArchMC Lifesteal", font_small, GRAY)
    
    # Background with slight blur
    bg = Image.open(TEMPLATE_PATH).convert("RGBA")
    bg = bg.resize((card_width, card_height), Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=3))
    dark_overlay = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 80))
    bg = Image.alpha_composite(bg, dark_overlay)
    
    final = Image.alpha_composite(bg, card)
    
    buf = io.BytesIO()
    final.save(buf, format="PNG")
    buf.seek(0)
    return buf

YEARLY_STATS_FILE = "yearly_stats.json"
ERROR_LOG_CHANNEL_ID = 1454137711710703785

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger('archie-bot')
load_dotenv()
bot = discord.Bot()

async def log_error_to_channel(command: str, user: discord.User, guild: Optional[discord.Guild], error: Exception, extra: Optional[dict] = None):
    """Send error details to the error logging channel."""
    try:
        channel = bot.get_channel(ERROR_LOG_CHANNEL_ID)
        if not channel:
            channel = await bot.fetch_channel(ERROR_LOG_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="⚠️ Command Error",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Command", value=f"`/{command}`", inline=True)
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
            embed.add_field(name="Guild", value=f"{guild.name} ({guild.id})" if guild else "DM", inline=True)
            embed.add_field(name="Error", value=f"```{type(error).__name__}: {str(error)[:500]}```", inline=False)
            if extra:
                for k, v in extra.items():
                    embed.add_field(name=k, value=f"`{v}`", inline=True)
            await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to log error to channel: {e}")

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

# Yearly stats persistence (using safe JSON operations)
def load_yearly_stats():
    default = {
        "year": datetime.now().year,
        "commands": defaultdict(int),
        "total_commands": 0,
        "guild_usage": defaultdict(int),
        "guild_names": {},
    }
    data = safe_json_load(YEARLY_STATS_FILE, {})
    if data:
        return {
            "year": data.get("year", datetime.now().year),
            "commands": defaultdict(int, data.get("commands", {})),
            "total_commands": data.get("total_commands", 0),
            "guild_usage": defaultdict(int, data.get("guild_usage", {})),
            "guild_names": data.get("guild_names", {}),
        }
    return default

def save_yearly_stats():
    data = {
        "year": yearly_stats["year"],
        "commands": dict(yearly_stats["commands"]),
        "total_commands": yearly_stats["total_commands"],
        "guild_usage": dict(yearly_stats["guild_usage"]),
        "guild_names": yearly_stats["guild_names"],
    }
    safe_json_save(YEARLY_STATS_FILE, data)

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
    if check_cooldown(ctx.author.id):
        await ctx.respond("Please wait a few seconds before using commands again.", ephemeral=True)
        return
    
    safe_username = sanitize_username(username)
    if not safe_username:
        await ctx.respond("Invalid username.", ephemeral=True)
        return
    if is_username_blocked(safe_username):
        await ctx.respond("That username cannot be looked up.", ephemeral=True)
        return
    
    await ctx.defer()
    try:
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
        
        client = get_api_client()
        data = await client.get(f"/v1/economy/player/username/{safe_username}")
        
        if data and isinstance(data, dict):
            balances = data.get("balances", {})
            if not balances:
                await ctx.respond(f"No balance data found for {safe_username}.")
                return
            if bal_type in balances:
                bal = balances[bal_type]
                embed = discord.Embed(
                    title=f"💰 {gamemode.capitalize()} Balance for {safe_username}",
                    description=f"**{bal:,}**",
                    color=discord.Color.gold()
                )
                embed.set_footer(text=f"ArchMC {gamemode.capitalize()} • Official API")
                await ctx.respond(embed=embed)
            else:
                bal_lines = [f"**{k.replace('-', ' ').title()}**: `{v:,}`" for k, v in balances.items()]
                embed = discord.Embed(
                    title=f"💰 All Balances for {safe_username}",
                    description="\n".join(bal_lines),
                    color=discord.Color.gold()
                )
                embed.set_footer(text="ArchMC Economy • Official API")
                await ctx.respond(embed=embed)
        else:
            await ctx.respond(f"No balance profile found for **{safe_username}**.")
    except Exception as e:
        logger.error(f"balance error: {e}")
        await log_error_to_channel("balance", ctx.author, ctx.guild, e, {"username": safe_username, "gamemode": gamemode})
        await ctx.respond("Failed to fetch balance. Please try again later.")

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
    if check_cooldown(ctx.author.id):
        await ctx.respond("Please wait a few seconds before using commands again.", ephemeral=True)
        return
    
    await ctx.defer()
    try:
        client = get_api_client()
        data = await client.get(f"/v1/leaderboards/{statid}?page=0&size=10")
        if data and isinstance(data, dict):
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
            await ctx.respond("No duel leaderboard data found.")
    except Exception as e:
        logger.error(f"dueltop error: {e}")
        await log_error_to_channel("dueltop", ctx.author, ctx.guild, e, {"statid": statid})
        await ctx.respond("Failed to fetch duel leaderboard. Please try again later.")

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
    if check_cooldown(ctx.author.id):
        await ctx.respond("Please wait a few seconds before using commands again.", ephemeral=True)
        return
    
    safe_username = sanitize_username(username)
    if not safe_username:
        await ctx.respond("Invalid username.", ephemeral=True)
        return
    if is_username_blocked(safe_username):
        await ctx.respond("That username cannot be looked up.", ephemeral=True)
        return
    
    await ctx.defer()
    try:
        client = get_api_client()
        data = await client.get(f"/v1/players/username/{safe_username}/statistics")
        if data and isinstance(data, dict):
            statistics = data.get("statistics", {})
            duel_stats = {k: v for k, v in statistics.items() if k.startswith("elo:") or k.startswith("wins:")}
            logger.info(f"[duelstats] username={safe_username} duel_stats_keys={list(duel_stats.keys())}")
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
                    embed = build_duelstats_embed(data, safe_username, mode_stats, mode_labels, mode_keys, page, 4)
                    view = DuelStatsView(data, safe_username, mode_stats, mode_labels, mode_keys, page)
                    await ctx.respond(embed=embed, view=view)
                except Exception as group_exc:
                    logger.error(f"[duelstats] Grouping error for {safe_username}: {group_exc}")
                    await ctx.respond("Failed to format duel stats.")
            else:
                await ctx.respond("No duel stats found for that player.")
        else:
            await ctx.respond("No duel stats found for that player.")
    except Exception as e:
        logger.error(f"[duelstats] Exception for {safe_username}: {e}")
        await log_error_to_channel("duelstats", ctx.author, ctx.guild, e, {"username": safe_username})
        await ctx.respond("Failed to fetch duel stats. Please try again later.")


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
    if check_cooldown(ctx.author.id):
        await ctx.respond("Please wait a few seconds before using commands again.", ephemeral=True)
        return
    
    await ctx.defer()
    try:
        client = get_api_client()
        leaderboard = await client.get_ugc_leaderboard("trojan", stat)
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
        logger.error(f"lifetop error: {e}")
        await log_error_to_channel("lifetop", ctx.author, ctx.guild, e, {"stat": stat})
        await ctx.respond("Failed to fetch leaderboard. Please try again later.")

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
    # Rate limit check
    if check_cooldown(ctx.author.id):
        await ctx.respond("Please wait a few seconds before using commands again.", ephemeral=True)
        return
    
    # Username sanitization
    safe_username = sanitize_username(username)
    if not safe_username:
        await ctx.respond("Invalid username. Use only letters, numbers, and underscores (max 16 chars).", ephemeral=True)
        return
    if is_username_blocked(safe_username):
        await ctx.respond("That username cannot be looked up.", ephemeral=True)
        return
    
    await ctx.defer()
    try:
        client = get_api_client()
        # Async API calls
        stats, profile = await asyncio.gather(
            client.get(f"/v1/ugc/trojan/players/username/{safe_username}/statistics"),
            client.get(f"/v1/ugc/trojan/players/username/{safe_username}/profile"),
            return_exceptions=True
        )
        
        if isinstance(stats, Exception):
            stats = None
        if isinstance(profile, Exception):
            profile = None
            
        if stats and isinstance(stats, dict):
            username_disp = stats.get("username", safe_username)
            uuid = stats.get("uuid", "")
            statistics = stats.get("statistics", {})
            
            # Fetch head async (non-blocking)
            head_data = await fetch_player_head(uuid)
            
            # Generate card in thread pool to prevent CPU blocking
            try:
                loop = asyncio.get_event_loop()
                card = await loop.run_in_executor(
                    None, 
                    generate_lifestats_card, 
                    username_disp, uuid, statistics, profile or {}, head_data
                )
                file = discord.File(card, filename="lifestats.png")
                await ctx.respond(file=file)
            except Exception as card_error:
                logger.error(f"Failed to generate card: {card_error}")
                # Fallback to embed
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
                for k, v in statistics.items():
                    emoji = stat_emojis.get(k, "📈")
                    name = f"{emoji} {k.capitalize()}"
                    value_lines = []
                    if isinstance(v, dict) and "value" in v:
                        value_lines.append(f"Value: `{v.get('value', 0)}`")
                        if v.get('position') is not None:
                            value_lines.append(f"Rank: `#{v.get('position'):,}`")
                    else:
                        value_lines.append(f"Value: `{v}`")
                    embed.add_field(name=name, value="\n".join(value_lines), inline=True)
                embed.set_footer(text="ArchMC Lifesteal • Official API")
                await ctx.respond(embed=embed)
        else:
            await ctx.respond("No stats found for that player.")
    except Exception as e:
        logger.error(f"lifestats error: {e}")
        await log_error_to_channel("lifestats", ctx.author, ctx.guild, e, {"username": safe_username})
        await ctx.respond("Failed to fetch stats. Please try again later.")

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
    if check_cooldown(ctx.author.id):
        await ctx.respond("Please wait a few seconds before using commands again.", ephemeral=True)
        return
    
    safe_username = sanitize_username(username)
    if not safe_username:
        await ctx.respond("Invalid username.", ephemeral=True)
        return
    if is_username_blocked(safe_username):
        await ctx.respond("That username cannot be looked up.", ephemeral=True)
        return
    
    await ctx.defer()
    try:
        client = get_api_client()
        stat_info = await client.get(f"/v1/ugc/trojan/players/username/{safe_username}/statistics/{stat}")
        if stat_info and isinstance(stat_info, dict) and "value" in stat_info:
            embed = stat_to_embed(stat_info, stat, safe_username)
            await ctx.respond(embed=embed)
        else:
            stats = await client.get_ugc_player_stats_by_username("trojan", safe_username)
            stat_val = stats["statistics"].get(stat) if stats and "statistics" in stats and stat in stats["statistics"] else None
            if stat_val is not None:
                if not isinstance(stat_val, dict):
                    stat_val = {"value": stat_val}
                embed = stat_to_embed(stat_val, stat, safe_username)
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No data found for that player/stat.")
    except Exception as e:
        logger.error(f"lifestat error: {e}")
        await log_error_to_channel("lifestat", ctx.author, ctx.guild, e, {"username": safe_username, "stat": stat})
        await ctx.respond("Failed to fetch stat. Please try again later.")


# /clantop - Top Clans Leaderboard
@bot.slash_command(name="clantop", description="Show the top clans from ArchMC")
async def clantop(ctx: discord.ApplicationContext):
    if check_cooldown(ctx.author.id):
        await ctx.respond("Please wait a few seconds before using commands again.", ephemeral=True)
        return
    
    await ctx.defer()
    try:
        client = get_api_client()
        data = await client.get("/v1/ugc/trojan/clans?page=0&size=10")
        if data and isinstance(data, dict):
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
            await ctx.respond("No clan leaderboard data found.")
    except Exception as e:
        logger.error(f"clantop error: {e}")
        await log_error_to_channel("clantop", ctx.author, ctx.guild, e)
        await ctx.respond("Failed to fetch clan leaderboard. Please try again later.")


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
    error_text = traceback.format_exc()
    logger.error(f"Error in event {event}:\n{error_text}")
    # Prevent recursive crashes - wrap in try/except and don't re-raise
    try:
        channel = bot.get_channel(BOT_ERRORS_CHANNEL)
        if channel:
            # Truncate and sanitize error message
            error_msg = f"⚠️ Error in event `{event}`:\n```py\n{error_text[:1800]}```"
            await asyncio.wait_for(channel.send(error_msg), timeout=5.0)
    except Exception as send_error:
        logger.error(f"Failed to send error notification: {send_error}")


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
    if check_cooldown(ctx.author.id):
        await ctx.respond("Please wait a few seconds before using commands again.", ephemeral=True)
        return
    
    await ctx.defer()
    try:
        client = get_api_client()
        gamemode = "trojan" if mode == "lifesteal" else "spartan"
        leaderboard = await client.get(f"/v1/ugc/{gamemode}/leaderboard/playtime?page=0&size=10")
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
        logger.error(f"playtime error: {e}")
        await log_error_to_channel("playtime", ctx.author, ctx.guild, e, {"mode": mode})
        await ctx.respond("Failed to fetch playtime leaderboard. Please try again later.")


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
    if check_cooldown(ctx.author.id):
        await ctx.respond("Please wait a few seconds before using commands again.", ephemeral=True)
        return
    
    await ctx.defer()
    try:
        client = get_api_client()
        data = await client.get(f"/v1/economy/baltop/{type}")
        if data and isinstance(data, dict):
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
            await ctx.respond("No baltop data found for that type.")
    except Exception as e:
        logger.error(f"baltop error: {e}")
        await log_error_to_channel("baltop", ctx.author, ctx.guild, e, {"type": type})
        await ctx.respond("Failed to fetch baltop leaderboard. Please try again later.")

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


class AsyncPIGDIClient:
    """Async API client - prevents blocking the event loop."""
    BASE_URL = "https://api.arch.mc"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(
                headers={"X-API-KEY": self.api_key},
                timeout=timeout
            )
        return self._session

    async def _request(self, method: str, path: str) -> Any:
        session = await self._get_session()
        url = f"{self.BASE_URL}{path}"
        try:
            async with session.request(method, url) as resp:
                if resp.status != 200:
                    return None
                if resp.content_type and resp.content_type.startswith("application/json"):
                    return await resp.json()
                return await resp.text()
        except asyncio.TimeoutError:
            logger.warning(f"API timeout: {path}")
            return None
        except Exception as e:
            logger.error(f"API error: {e}")
            return None

    async def get_ugc_player_stats_by_username(self, gamemode: str, username: str) -> Optional[Dict]:
        path = f"/v1/ugc/{gamemode}/players/username/{username}/statistics"
        return await self._request("GET", path)

    async def get_ugc_leaderboard(self, gamemode: str, stat_type: str, page: int = 0, size: int = 10) -> Optional[Dict]:
        path = f"/v1/ugc/{gamemode}/leaderboard/{stat_type}?page={page}&size={size}"
        return await self._request("GET", path)

    async def get(self, path: str) -> Optional[Dict]:
        return await self._request("GET", path)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

# Global async client instance
_api_client: Optional[AsyncPIGDIClient] = None

def get_api_client() -> AsyncPIGDIClient:
    global _api_client
    if _api_client is None:
        API_KEY = os.getenv("ARCH_API_KEY") or "your-api-key-here"
        _api_client = AsyncPIGDIClient(API_KEY)
    return _api_client

# Example usage
if __name__ == "__main__":
    bot.run(os.getenv('TOKEN')) # run the bot with the token
