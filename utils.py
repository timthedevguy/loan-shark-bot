"""
Utility functions for the Loan Shark Bot
"""
from models import Config


async def get_guild_config(guild_id: int) -> Config:
    """Get or create guild configuration"""
    config, created = await Config.get_or_create(
        guild_id=guild_id,
        defaults={
            "currency_prefix": "$",
            "currency_suffix": None
        }
    )
    return config


async def format_currency(guild_id: int, amount: float) -> str:
    """Format currency with guild-specific prefix/suffix"""
    config = await get_guild_config(guild_id)
    return config.format_currency(amount)

