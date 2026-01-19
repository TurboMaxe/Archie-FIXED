"""Main bot setup and event handlers for Archie."""

import logging
import traceback

import discord

from .config import config

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s:%(name)s: %(message)s"
)
logger = logging.getLogger("archie-bot")

bot = discord.Bot()

COGS = [
    "archie.cogs.economy",
    "archie.cogs.lifesteal",
    "archie.cogs.duels",
    "archie.cogs.misc",
]


@bot.event
async def on_ready() -> None:
    logger.info(f"{bot.user} is ready and online! Registering commands...")
    await bot.sync_commands()
    logger.info(f"{bot.user} commands synced!")

    try:
        channel = bot.get_channel(1454137711710703783)
        if channel:
            await channel.send(
                "✅ Archie slash commands are now fully synced and ready to use!"
            )
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


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    channel = bot.get_channel(config.GUILD_JOIN_CHANNEL)
    if channel:
        await channel.send(f"✅ Joined guild: **{guild.name}** (ID: {guild.id})")


@bot.event
async def on_guild_remove(guild: discord.Guild) -> None:
    channel = bot.get_channel(config.GUILD_LEAVE_CHANNEL)
    if channel:
        await channel.send(f"❌ Left guild: **{guild.name}** (ID: {guild.id})")


@bot.event
async def on_error(event: str, *args, **kwargs) -> None:
    logger.error(f"Error in event {event}:\n{traceback.format_exc()}")
    channel = bot.get_channel(config.BOT_ERRORS_CHANNEL)
    if channel:
        error_msg = f"⚠️ Error in event `{event}`:\n```py\n{traceback.format_exc()}```"
        await channel.send(error_msg[:2000])


@bot.event
async def on_application_command(ctx: discord.ApplicationContext) -> None:
    logger.info(
        f"/{ctx.command.name} used by {ctx.author} in {getattr(ctx.guild, 'name', 'DM')}"
    )


def load_cogs() -> None:
    """Load all cogs."""
    for cog in COGS:
        try:
            bot.load_extension(cog)
            logger.info(f"Loaded cog: {cog}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog}: {e}")


def run() -> None:
    """Run the bot."""
    load_cogs()
    bot.run(config.TOKEN)
