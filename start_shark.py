"""
Loan Shark Bot - A Discord bot for managing loans between server members
"""

import os

import discord
import sentry_sdk
from discord.ext import commands
from dotenv import load_dotenv

from database import close_db, init_db
from models import Config

# Load environment variables
load_dotenv()

# Get configuration from environment
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SENTRY_DSN = os.getenv("SENTRY_DSN")
GUILD_IDS = [
    int(guild_id.strip())
    for guild_id in os.getenv("GUILD_IDS", "").split(",")
    if guild_id.strip()
]

# Initialize Sentry if DSN is provided
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN)

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,  # We'll use our custom help command
)


async def load_cogs():
    """Load all command cogs"""
    cogs = ["cogs.loan_commands", "cogs.general_commands"]

    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"Loaded cog: {cog}")
        except Exception as e:
            print(f"Failed to load cog {cog}: {e}")


@bot.event
async def setup_hook():
    """Called when the bot is setting up (before connecting to Discord)"""
    print("Initializing database...")
    await init_db()
    guild_ids = await Config.all().values_list("guild_id", flat=True)
    print(f"Guilds in database: {list(guild_ids)}")
    print("Loading cogs...")
    await load_cogs()
    print("Syncing slash commands...")
    try:
        for guild_id in GUILD_IDS:
            guild = discord.Object(id=guild_id)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} slash command(s) to guild {guild_id}")

        # synced = await bot.tree.sync()
        # print(f"Synced {len(synced)} slash command(s) globally")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_ready():
    """Called when the bot is ready"""
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guild(s)")
    print("------")

    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="your loans | /help"
        )
    )
    print("Bot is ready!")


@bot.event
async def on_command_error(ctx, error):
    """Global error handler for prefix commands (legacy)"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `/help` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ Missing required argument: `{error.param.name}`. Use `/help {ctx.command.name}` for usage info."
        )
    elif isinstance(error, commands.BadArgument):
        await ctx.send(
            f"❌ Invalid argument. Use `/help {ctx.command.name}` for usage info."
        )
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send(
            "❌ I don't have the necessary permissions to execute this command!"
        )
    else:
        # Log unexpected errors
        print(f"Error in command {ctx.command}: {error}")
        await ctx.send("❌ An unexpected error occurred. Please try again later.")

        # Send to Sentry if configured
        if SENTRY_DSN:
            sentry_sdk.capture_exception(error)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
):
    """Global error handler for slash commands"""
    if isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command!", ephemeral=True
        )
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"❌ This command is on cooldown. Try again in {error.retry_after:.1f}s",
            ephemeral=True,
        )
    else:
        # Log unexpected errors
        print(
            f"Error in app command {interaction.command.name if interaction.command else 'unknown'}: {error}"
        )

        if interaction.response.is_done():
            await interaction.followup.send(
                "❌ An unexpected error occurred. Please try again later.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "❌ An unexpected error occurred. Please try again later.",
                ephemeral=True,
            )

        # Send to Sentry if configured
        if SENTRY_DSN:
            sentry_sdk.capture_exception(error)


@bot.event
async def on_message(message):
    """Called when a message is sent"""
    # Ignore messages from bots
    if message.author.bot:
        return

    # Process commands
    await bot.process_commands(message)


async def main():
    """Main function to start the bot"""
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables!")
        print("Please create a .env file with your Discord bot token.")
        print("See .env.example for reference.")
        return

    async with bot:
        # Start the bot (setup_hook will handle initialization)
        try:
            await bot.start(DISCORD_TOKEN)
        except KeyboardInterrupt:
            print("\nShutting down bot...")
        finally:
            await close_db()


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped.")
