"""
General utility commands for the Discord bot
"""
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from utils import get_guild_config


class SetCurrencyModal(discord.ui.Modal, title="Set Currency Format"):
    prefix = discord.ui.TextInput(
        label="Prefix (e.g. $, €, £)",
        placeholder="Leave blank for no prefix",
        required=False,
        max_length=10,
    )
    suffix = discord.ui.TextInput(
        label="Suffix (e.g. ISK, USD, coins)",
        placeholder="Leave blank for no suffix — a space will be added before it automatically",
        required=False,
        max_length=10,
    )

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.prefix.default = config.currency_prefix or ""
        self.suffix.default = (config.currency_suffix or "").lstrip(" ")

    async def on_submit(self, interaction: discord.Interaction):
        prefix = self.prefix.value if self.prefix.value != "" else None
        suffix = f" {self.suffix.value}" if self.suffix.value != "" else None

        self.config.currency_prefix = prefix
        self.config.currency_suffix = suffix
        await self.config.save()

        example = self.config.format_currency(123.45)

        embed = discord.Embed(
            title="💱 Currency Format Updated",
            description="Currency display has been updated for this server",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Prefix", value=f"`{prefix}`" if prefix else "None", inline=True)
        embed.add_field(name="Suffix", value=f"`{suffix}`" if suffix else "None", inline=True)
        embed.add_field(name="Example", value=example, inline=False)
        embed.set_footer(text="Only administrators can change this setting")

        await interaction.response.send_message(embed=embed, ephemeral=True)


class GeneralCommands(commands.Cog):
    """General utility commands"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Check the bot's response time"""
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: {latency}ms",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="info", description="Show bot information")
    async def info(self, interaction: discord.Interaction):
        """Display bot information"""
        embed = discord.Embed(
            title="🦈 Loan Shark Bot",
            description="A Discord bot for managing loans between server members",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Servers", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Users", value=len(self.bot.users), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.set_footer(text=f"Made with discord.py {discord.__version__}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setcurrency", description="Set currency prefix/suffix (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def setcurrency(self, interaction: discord.Interaction):
        """Opens a modal to set the currency display format for this server (Admin only)"""
        config = await get_guild_config(interaction.guild.id)
        await interaction.response.send_modal(SetCurrencyModal(config))


async def setup(bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(GeneralCommands(bot))



