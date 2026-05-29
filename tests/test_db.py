"""
Test script to verify database initialization works correctly
"""
import asyncio
from database import init_db, close_db
from models import User, Loan, Config


async def test_database():
    """Test database operations"""
    print("Testing database initialization...")

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

        # Clean up
        await config.delete()
        await user.delete()
        print("✓ Cleaned up test data")

        # Close database
        await close_db()
        print("✓ Database closed successfully")

        print("\n✅ All database tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_database())


