"""
Test script to verify database initialization works correctly
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite://tests/db.sqlite3")
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from database import init_db, close_db
from models import User, Config


async def test_database():
    """Test database operations"""
    print("Testing database initialization...")
    config = None
    user = None

    try:
        # Initialize database
        await init_db()
        print("✓ Database initialized successfully")

        # Test creating a config
        config = await Config.create(
            guild_id=123456789,
            currency_prefix="$",
            currency_suffix=None
        )
        print(f"✓ Created test config for guild: {config.guild_id}")

        # Test currency formatting
        formatted = config.format_currency(123.45)
        print(f"✓ Currency formatting works: {formatted}")

        # Test changing currency
        config.currency_prefix = "€"
        config.currency_suffix = " EUR"
        await config.save()
        formatted2 = config.format_currency(123.45)
        print(f"✓ Updated currency format: {formatted2}")

        # Test creating a user
        user = await User.create(
            discord_id=987654321,
            username="TestUser"
        )
        print(f"✓ Created test user: {user.username}")

        # Test querying the user
        found_user = await User.get(discord_id=987654321)
        print(f"✓ Found user: {found_user.username}")

        print("\n✅ All database tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up test data and always close the database, even on failure,
        # so the script exits instead of hanging on a stale connection
        if config:
            await config.delete()
        if user:
            await user.delete()
        await close_db()
        print("✓ Database closed")


if __name__ == "__main__":
    asyncio.run(test_database())
