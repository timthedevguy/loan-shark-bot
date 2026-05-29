"""
Loan management commands for the Discord bot
"""

from datetime import datetime, timezone
from decimal import Decimal

import discord
from discord import app_commands
from discord.ext import commands

from models import Loan, Transaction, User
from utils import get_guild_config


class LoanCommands(commands.Cog):
    """Commands for managing loans"""

    def __init__(self, bot):
        self.bot = bot

    async def get_or_create_user(self, discord_user: discord.User) -> User:
        """Get or create a user in the database"""
        user, created = await User.get_or_create(
            discord_id=discord_user.id, defaults={"username": discord_user.name}
        )
        if not created and user.username != discord_user.name:
            user.username = discord_user.name
            await user.save()
        return user

    @app_commands.command(name="lend", description="Create a new loan")
    @app_commands.describe(
        member="The person you are lending money to",
        amount="The amount of money to lend",
        description="Optional description for the loan"
    )
    async def lend(
        self, interaction: discord.Interaction, member: discord.User, amount: float, description: str = None
    ):
        """Lend money to another user"""
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be greater than 0!", ephemeral=True)
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ You cannot lend money to yourself!", ephemeral=True)
            return

        lender = await self.get_or_create_user(interaction.user)
        borrower = await self.get_or_create_user(member)

        # Check for existing unpaid loan between these users
        existing_loan = await Loan.get_or_none(
            lender=lender, borrower=borrower, is_paid=False
        )

        # Get currency formatting
        config = await get_guild_config(interaction.guild.id)

        if existing_loan:
            # Consolidate: add to existing loan
            old_amount = existing_loan.amount
            new_amount = old_amount + Decimal(str(amount))
            existing_loan.amount = new_amount

            # Update description if new one provided
            if description:
                if existing_loan.description:
                    existing_loan.description += f" | {description}"
                else:
                    existing_loan.description = description

            await existing_loan.save()

            embed = discord.Embed(
                title="💰 Loan Consolidated",
                description=f"Added to existing loan #{existing_loan.id}",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Lender", value=interaction.user.mention, inline=True)
            embed.add_field(name="Borrower", value=member.mention, inline=True)
            embed.add_field(
                name="Added Amount", value=config.format_currency(amount), inline=True
            )
            embed.add_field(
                name="Previous Total",
                value=config.format_currency(float(old_amount)),
                inline=True,
            )
            embed.add_field(
                name="New Total",
                value=config.format_currency(float(new_amount)),
                inline=True,
            )
            embed.add_field(name="Loan ID", value=f"#{existing_loan.id}", inline=True)
            if existing_loan.description:
                embed.add_field(
                    name="Description", value=existing_loan.description, inline=False
                )

            await interaction.response.send_message(embed=embed)
        else:
            # Create new loan
            loan = await Loan.create(
                lender=lender,
                borrower=borrower,
                amount=Decimal(str(amount)),
                description=description,
            )

            embed = discord.Embed(
                title="💰 New Loan Created",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Lender", value=interaction.user.mention, inline=True)
            embed.add_field(name="Borrower", value=member.mention, inline=True)
            embed.add_field(
                name="Amount", value=config.format_currency(amount), inline=True
            )
            embed.add_field(name="Loan ID", value=f"#{loan.id}", inline=True)
            if description:
                embed.add_field(name="Description", value=description, inline=False)

            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="repay", description="Record a loan repayment")
    @app_commands.describe(
        loan_id="The ID of the loan to repay",
        amount="The amount being repaid",
        note="Optional note about the payment"
    )
    async def repay(self, interaction: discord.Interaction, loan_id: int, amount: float, note: str = None):
        """Record a repayment on a loan"""
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be greater than 0!", ephemeral=True)
            return

        loan = await Loan.get_or_none(id=loan_id).prefetch_related(
            "lender", "borrower", "transactions"
        )

        if not loan:
            await interaction.response.send_message(f"❌ Loan #{loan_id} not found!", ephemeral=True)
            return

        user = await self.get_or_create_user(interaction.user)

        # Only the lender can record repayments
        if user.id != loan.lender.id:
            await interaction.response.send_message("❌ Only the lender can record repayments!", ephemeral=True)
            return

        if loan.is_paid:
            await interaction.response.send_message("❌ This loan is already marked as paid!", ephemeral=True)
            return

        transaction = await Transaction.create(
            loan=loan, amount=Decimal(str(amount)), note=note
        )

        # Calculate total paid so far
        transactions = await Transaction.filter(loan=loan)
        total_paid = sum(t.amount for t in transactions)

        # Check if loan is fully paid
        if total_paid >= loan.amount:
            loan.is_paid = True
            loan.paid_at = datetime.now(timezone.utc)
            await loan.save()

        # Get currency formatting
        config = await get_guild_config(interaction.guild.id)

        embed = discord.Embed(
            title="💵 Payment Recorded",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Loan ID", value=f"#{loan.id}", inline=True)
        embed.add_field(
            name="Payment", value=config.format_currency(amount), inline=True
        )
        embed.add_field(
            name="Total Paid",
            value=config.format_currency(float(total_paid)),
            inline=True,
        )
        embed.add_field(
            name="Total Due",
            value=config.format_currency(float(loan.amount)),
            inline=True,
        )
        embed.add_field(
            name="Remaining",
            value=config.format_currency(float(max(0, loan.amount - total_paid))),
            inline=True,
        )
        embed.add_field(
            name="Status",
            value="✅ Paid in Full" if loan.is_paid else "⏳ Pending",
            inline=True,
        )
        if note:
            embed.add_field(name="Note", value=note, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="myloans", description="View your loans (given and received)")
    async def my_loans(self, interaction: discord.Interaction):
        """View all loans for the current user"""
        user = await self.get_or_create_user(interaction.user)

        loans_given = await Loan.filter(lender=user, is_paid=False).prefetch_related(
            "borrower"
        )
        loans_received = await Loan.filter(
            borrower=user, is_paid=False
        ).prefetch_related("lender")

        # Get currency formatting
        config = await get_guild_config(interaction.guild.id)

        embed = discord.Embed(
            title=f"📊 Loans for {interaction.user.name}",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc),
        )

        if loans_given:
            loans_text = []
            total_owed = Decimal(0)
            for loan in loans_given:
                borrower_name = await self.bot.fetch_user(loan.borrower.discord_id)
                loans_text.append(
                    f"**#{loan.id}** - {borrower_name.mention}: {config.format_currency(float(loan.amount))}"
                )
                total_owed += loan.amount
            embed.add_field(
                name=f"💸 Money Lent (Total: {config.format_currency(float(total_owed))})",
                value="\n".join(loans_text),
                inline=False,
            )
        else:
            embed.add_field(
                name="💸 Money Lent", value="No active loans given", inline=False
            )

        if loans_received:
            loans_text = []
            total_debt = Decimal(0)
            for loan in loans_received:
                lender_name = await self.bot.fetch_user(loan.lender.discord_id)
                loans_text.append(
                    f"**#{loan.id}** - {lender_name.mention}: {config.format_currency(float(loan.amount))}"
                )
                total_debt += loan.amount
            embed.add_field(
                name=f"💳 Money Borrowed (Total: {config.format_currency(float(total_debt))})",
                value="\n".join(loans_text),
                inline=False,
            )
        else:
            embed.add_field(
                name="💳 Money Borrowed", value="No active loans received", inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="loan", description="View details of a specific loan")
    @app_commands.describe(loan_id="The ID of the loan to view")
    async def loan_details(self, interaction: discord.Interaction, loan_id: int):
        """View details of a specific loan"""
        loan = await Loan.get_or_none(id=loan_id).prefetch_related(
            "lender", "borrower", "transactions"
        )

        if not loan:
            await interaction.response.send_message(f"❌ Loan #{loan_id} not found!", ephemeral=True)
            return

        lender_user = await self.bot.fetch_user(loan.lender.discord_id)
        borrower_user = await self.bot.fetch_user(loan.borrower.discord_id)

        transactions = await Transaction.filter(loan=loan)
        total_paid = sum(t.amount for t in transactions)

        # Get currency formatting
        config = await get_guild_config(interaction.guild.id)

        embed = discord.Embed(
            title=f"📋 Loan Details - #{loan.id}",
            color=discord.Color.green() if loan.is_paid else discord.Color.orange(),
            timestamp=loan.created_at,
        )
        embed.add_field(name="Lender", value=lender_user.mention, inline=True)
        embed.add_field(name="Borrower", value=borrower_user.mention, inline=True)
        embed.add_field(
            name="Status", value="✅ Paid" if loan.is_paid else "⏳ Unpaid", inline=True
        )
        embed.add_field(
            name="Amount", value=config.format_currency(float(loan.amount)), inline=True
        )
        embed.add_field(
            name="Total Paid",
            value=config.format_currency(float(total_paid)),
            inline=True,
        )
        embed.add_field(
            name="Remaining",
            value=config.format_currency(float(max(0, loan.amount - total_paid))),
            inline=True,
        )
        embed.add_field(
            name="Created",
            value=loan.created_at.strftime("%Y-%m-%d %H:%M"),
            inline=True,
        )

        if loan.description:
            embed.add_field(name="Description", value=loan.description, inline=False)

        if transactions:
            trans_text = "\n".join(
                [
                    f"{config.format_currency(float(t.amount))} on {t.created_at.strftime('%Y-%m-%d')}"
                    for t in transactions[:5]
                ]
            )
            if len(transactions) > 5:
                trans_text += f"\n... and {len(transactions) - 5} more"
            embed.add_field(name="Recent Payments", value=trans_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="markpaid", description="Mark a loan as fully paid")
    @app_commands.describe(loan_id="The ID of the loan to mark as paid")
    async def mark_paid(self, interaction: discord.Interaction, loan_id: int):
        """Mark a loan as fully paid"""
        loan = await Loan.get_or_none(id=loan_id).prefetch_related("lender", "borrower")

        if not loan:
            await interaction.response.send_message(f"❌ Loan #{loan_id} not found!", ephemeral=True)
            return

        user = await self.get_or_create_user(interaction.user)

        # Only lender can mark as paid
        if user.id != loan.lender.id:
            await interaction.response.send_message("❌ Only the lender can mark this loan as paid!", ephemeral=True)
            return

        if loan.is_paid:
            await interaction.response.send_message("❌ This loan is already marked as paid!", ephemeral=True)
            return

        loan.is_paid = True
        loan.paid_at = datetime.now(timezone.utc)
        await loan.save()

        borrower_user = await self.bot.fetch_user(loan.borrower.discord_id)

        # Get currency formatting
        config = await get_guild_config(interaction.guild.id)

        embed = discord.Embed(
            title="✅ Loan Marked as Paid",
            description=f"Loan #{loan.id} has been marked as fully paid!",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Borrower", value=borrower_user.mention, inline=True)
        embed.add_field(
            name="Amount", value=config.format_currency(float(loan.amount)), inline=True
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(LoanCommands(bot))
