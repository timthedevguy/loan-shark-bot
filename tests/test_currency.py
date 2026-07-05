"""
Comprehensive test for currency customization feature
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite://tests/db.sqlite3")
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from database import init_db, close_db
from models import User, Loan
from utils import get_guild_config, format_currency
from decimal import Decimal


async def test_currency_feature():
    """Test the complete currency customization feature"""
    print("=" * 60)
    print("CURRENCY CUSTOMIZATION FEATURE - COMPREHENSIVE TEST")
    print("=" * 60)

    config = None
    config2 = None
    loan = None
    user1 = None
    user2 = None

    try:
        # Initialize database
        await init_db()
        print("\n✓ Database initialized")

        guild_id = 123456789

        # Test 1: Default currency
        print("\n[TEST 1] Default currency formatting...")
        config = await get_guild_config(guild_id)
        assert config.currency_prefix == "$"
        assert config.currency_suffix is None
        formatted = config.format_currency(100.50)
        assert formatted == "$100.50"
        print(f"  ✓ Default format: {formatted}")

        # Test 2: Euro prefix
        print("\n[TEST 2] Euro prefix...")
        config.currency_prefix = "€"
        await config.save()
        formatted = config.format_currency(100.50)
        assert formatted == "€100.50"
        print(f"  ✓ Euro format: {formatted}")

        # Test 3: Suffix only
        print("\n[TEST 3] Suffix only...")
        config.currency_prefix = ""
        config.currency_suffix = " USD"
        await config.save()
        formatted = config.format_currency(100.50)
        assert formatted == "100.50 USD"
        print(f"  ✓ Suffix format: {formatted}")

        # Test 4: Both prefix and suffix
        print("\n[TEST 4] Prefix + Suffix...")
        config.currency_prefix = "$"
        config.currency_suffix = " CAD"
        await config.save()
        formatted = config.format_currency(100.50)
        assert formatted == "$100.50 CAD"
        print(f"  ✓ Combined format: {formatted}")

        # Test 5: Custom text
        print("\n[TEST 5] Custom text...")
        config.currency_prefix = "Gold: "
        config.currency_suffix = " coins"
        await config.save()
        formatted = config.format_currency(100.50)
        assert formatted == "Gold: 100.50 coins"
        print(f"  ✓ Custom format: {formatted}")

        # Test 6: Unicode symbols
        print("\n[TEST 6] Unicode symbols...")
        config.currency_prefix = "¥"
        config.currency_suffix = None
        await config.save()
        formatted = config.format_currency(100.50)
        assert formatted == "¥100.50"
        print(f"  ✓ Yen format: {formatted}")

        config.currency_prefix = "₿"
        await config.save()
        formatted = config.format_currency(0.00123456)
        print(f"  ✓ Bitcoin format: {formatted}")

        # Test 7: Multiple guilds
        print("\n[TEST 7] Multiple guild configurations...")
        guild2_id = 987654321
        config2 = await get_guild_config(guild2_id)
        config2.currency_prefix = "£"
        await config2.save()

        # Verify both exist independently
        config1 = await get_guild_config(guild_id)
        assert config1.currency_prefix == "₿"
        assert config2.currency_prefix == "£"
        print(f"  ✓ Guild 1: {config1.format_currency(100)}")
        print(f"  ✓ Guild 2: {config2.format_currency(100)}")

        # Test 8: Integration with loans
        print("\n[TEST 8] Integration with loan amounts...")
        user1 = await User.create(discord_id=111, username="Lender")
        user2 = await User.create(discord_id=222, username="Borrower")

        loan = await Loan.create(
            lender=user1,
            borrower=user2,
            amount=Decimal("1000.00")
        )

        # Test with different currencies
        config.currency_prefix = "$"
        config.currency_suffix = None
        await config.save()
        print(f"  ✓ Loan amount: {config.format_currency(float(loan.amount))}")

        config.currency_prefix = "€"
        await config.save()
        print(f"  ✓ Loan in euros: {config.format_currency(float(loan.amount))}")

        # Test 9: Edge cases
        print("\n[TEST 9] Edge cases...")
        config.currency_prefix = "$"
        config.currency_suffix = None
        await config.save()

        # Zero amount
        formatted = config.format_currency(0.00)
        assert formatted == "$0.00"
        print(f"  ✓ Zero: {formatted}")

        # Large amount — format_currency adds a thousands separator
        formatted = config.format_currency(999999.99)
        assert formatted == "$999,999.99"
        print(f"  ✓ Large: {formatted}")

        # Small amount
        formatted = config.format_currency(0.01)
        assert formatted == "$0.01"
        print(f"  ✓ Small: {formatted}")

        # Negative (for display purposes)
        formatted = config.format_currency(-50.00)
        assert formatted == "$-50.00"
        print(f"  ✓ Negative: {formatted}")

        # Test 10: Format currency helper
        print("\n[TEST 10] Helper function...")
        formatted = await format_currency(guild_id, 500.00)
        assert formatted == "$500.00"
        print(f"  ✓ Helper function: {formatted}")

        print("\n" + "=" * 60)
        print("✅ ALL CURRENCY FEATURE TESTS PASSED!")
        print("=" * 60)
        print("\nFeature is production-ready! 🎉")

    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up test data and always close the database, even on failure,
        # so the script exits instead of hanging on a stale connection
        print("\n[CLEANUP] Removing test data...")
        if config:
            await config.delete()
        if config2:
            await config2.delete()
        if loan:
            await loan.delete()
        if user1:
            await user1.delete()
        if user2:
            await user2.delete()
        await close_db()
        print("  ✓ Database closed")


if __name__ == "__main__":
    asyncio.run(test_currency_feature())
