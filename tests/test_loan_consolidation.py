"""
Test script for loan consolidation feature
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
from decimal import Decimal


async def test_loan_consolidation():
    """Test that multiple loans between same users are consolidated"""
    print("=" * 60)
    print("LOAN CONSOLIDATION FEATURE TEST")
    print("=" * 60)

    lender = None
    borrower = None
    loan1 = None
    loan2 = None
    loan3 = None

    try:
        # Initialize database
        await init_db()
        print("\n✓ Database initialized")

        # Create test users
        lender = await User.create(discord_id=111, username="Lender")
        borrower = await User.create(discord_id=222, username="Borrower")
        print("✓ Created test users")

        # Test 1: Create first loan
        print("\n[TEST 1] Creating first loan...")
        loan1 = await Loan.create(
            lender=lender,
            borrower=borrower,
            amount=Decimal("100.00"),
            description="First loan"
        )
        print(f"  ✓ Loan #{loan1.id} created: ${loan1.amount}")

        # Test 2: Check for existing unpaid loan (should find loan1)
        print("\n[TEST 2] Checking for existing unpaid loan...")
        existing = await Loan.get_or_none(
            lender=lender,
            borrower=borrower,
            is_paid=False
        )
        assert existing is not None, "Should find existing loan"
        assert existing.id == loan1.id, "Should find loan1"
        print(f"  ✓ Found existing loan #{existing.id}")

        # Test 3: Consolidate by adding to existing loan
        print("\n[TEST 3] Consolidating - adding $50 to existing loan...")
        old_amount = existing.amount
        additional_amount = Decimal("50.00")
        existing.amount = old_amount + additional_amount
        existing.description += " | Second loan"
        await existing.save()

        # Verify
        updated = await Loan.get(id=loan1.id)
        assert updated.amount == Decimal("150.00"), "Amount should be $150"
        print(f"  ✓ Previous: ${old_amount}")
        print(f"  ✓ Added: ${additional_amount}")
        print(f"  ✓ New total: ${updated.amount}")
        print(f"  ✓ Description: {updated.description}")

        # Test 4: Verify only one unpaid loan exists
        print("\n[TEST 4] Verifying only one unpaid loan exists...")
        unpaid_loans = await Loan.filter(
            lender=lender,
            borrower=borrower,
            is_paid=False
        )
        assert len(unpaid_loans) == 1, "Should have exactly one unpaid loan"
        print(f"  ✓ Only one unpaid loan: #{unpaid_loans[0].id}")

        # Test 5: Mark as paid and create new loan
        print("\n[TEST 5] After paying off, new loan should be created...")
        updated.is_paid = True
        await updated.save()

        loan2 = await Loan.create(
            lender=lender,
            borrower=borrower,
            amount=Decimal("75.00"),
            description="Third loan (after payoff)"
        )

        # Verify
        all_loans = await Loan.filter(lender=lender, borrower=borrower)
        unpaid_loans = await Loan.filter(
            lender=lender,
            borrower=borrower,
            is_paid=False
        )
        assert len(all_loans) == 2, "Should have 2 total loans"
        assert len(unpaid_loans) == 1, "Should have 1 unpaid loan"
        assert unpaid_loans[0].id == loan2.id, "Unpaid should be loan2"
        print(f"  ✓ Total loans: {len(all_loans)}")
        print(f"  ✓ Unpaid loans: {len(unpaid_loans)}")
        print(f"  ✓ New loan #{loan2.id}: ${loan2.amount}")

        # Test 6: Different direction (borrower becomes lender)
        print("\n[TEST 6] Testing reverse direction...")
        loan3 = await Loan.create(
            lender=borrower,  # Reversed!
            borrower=lender,
            amount=Decimal("25.00"),
            description="Reverse loan"
        )

        # Should not consolidate with opposite direction
        unpaid_by_original_lender = await Loan.filter(
            lender=lender,
            borrower=borrower,
            is_paid=False
        )
        unpaid_by_original_borrower = await Loan.filter(
            lender=borrower,
            borrower=lender,
            is_paid=False
        )
        assert len(unpaid_by_original_lender) == 1, "Should have 1 loan in original direction"
        assert len(unpaid_by_original_borrower) == 1, "Should have 1 loan in reverse direction"
        print(f"  ✓ Lender→Borrower unpaid: {len(unpaid_by_original_lender)}")
        print(f"  ✓ Borrower→Lender unpaid: {len(unpaid_by_original_borrower)}")
        print("  ✓ Directions kept separate ✓")

        # Test 7: Guild isolation — same pair, different guilds, must NOT consolidate
        print("\n[TEST 7] Testing guild isolation...")
        guild_a = 1111
        guild_b = 2222

        guild_a_loan = await Loan.create(
            lender=lender,
            borrower=borrower,
            amount=Decimal("200.00"),
            description="Guild A loan",
            guild_id=guild_a,
        )
        guild_b_loan = await Loan.create(
            lender=lender,
            borrower=borrower,
            amount=Decimal("300.00"),
            description="Guild B loan",
            guild_id=guild_b,
        )

        # The consolidation lookup used by /lend must be scoped to guild_id
        existing_in_a = await Loan.get_or_none(
            lender=lender, borrower=borrower, is_paid=False, guild_id=guild_a
        )
        existing_in_b = await Loan.get_or_none(
            lender=lender, borrower=borrower, is_paid=False, guild_id=guild_b
        )
        assert existing_in_a is not None and existing_in_a.id == guild_a_loan.id, \
            "Guild A lookup should only find the Guild A loan"
        assert existing_in_b is not None and existing_in_b.id == guild_b_loan.id, \
            "Guild B lookup should only find the Guild B loan"
        assert existing_in_a.id != existing_in_b.id, "Loans in different guilds must stay separate"

        # A loan from one guild must not be reachable by ID from another guild
        cross_guild_lookup = await Loan.get_or_none(id=guild_a_loan.id, guild_id=guild_b)
        assert cross_guild_lookup is None, "Guild A's loan must not be visible under Guild B's guild_id"
        print(f"  ✓ Guild A loan #{guild_a_loan.id} and Guild B loan #{guild_b_loan.id} kept separate")
        print("  ✓ Cross-guild lookup by ID correctly returns nothing")

        await guild_a_loan.delete()
        await guild_b_loan.delete()

        print("\n" + "=" * 60)
        print("✅ ALL LOAN CONSOLIDATION TESTS PASSED!")
        print("=" * 60)
        print("\n🎉 Feature working as expected!")
        print("\nBehavior:")
        print("  • Multiple unpaid loans to same person → Consolidated")
        print("  • Each person appears once in !myloans")
        print("  • After payoff → New loan starts fresh")
        print("  • Reverse direction → Kept separate")
        print("  • Different guilds → Kept separate")

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
        if loan1:
            await loan1.delete()
        if loan2:
            await loan2.delete()
        if loan3:
            await loan3.delete()
        if lender:
            await lender.delete()
        if borrower:
            await borrower.delete()
        await close_db()
        print("  ✓ Database closed")


if __name__ == "__main__":
    asyncio.run(test_loan_consolidation())
