"""
Loan management commands for the Discord bot
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import discord
from discord import app_commands
from discord.ext import commands

from models import Loan, Transaction, User
from utils import get_guild_config


class DeleteLoanConfirmView(discord.ui.View):
    """Confirmation prompt for /deleteloan — only the invoking admin can act on it"""

    def __init__(self, loan: Loan, lender_str: str, borrower_str: str, amount_str: str, invoker_id: int):
        super().__init__(timeout=30)
        self.loan = loan
        self.lender_str = lender_str
        self.borrower_str = borrower_str
        self.amount_str = amount_str
        self.invoker_id = invoker_id
        self.message: discord.InteractionMessage | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message(
                "❌ Only the admin who ran this command can respond to it!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="⌛ Confirmation timed out — loan was **not** deleted.", embed=None, view=None
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Delete Loan", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await self.loan.delete()

        embed = discord.Embed(
            title="🗑️ Loan Deleted",
            description=f"Loan #{self.loan.id} has been permanently deleted.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Lender", value=self.lender_str, inline=True)
        embed.add_field(name="Borrower", value=self.borrower_str, inline=True)
        embed.add_field(name="Amount", value=self.amount_str, inline=True)

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            content="Deletion cancelled — loan was **not** deleted.", embed=None, view=None
        )


class CleanupConfirmView(discord.ui.View):
    """Confirmation prompt for /cleanup — only the invoking admin can act on it"""

    def __init__(self, loans: list[Loan], cutoff_days: int, invoker_id: int):
        super().__init__(timeout=30)
        self.loans = loans
        self.cutoff_days = cutoff_days
        self.invoker_id = invoker_id
        self.message: discord.InteractionMessage | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message(
                "❌ Only the admin who ran this command can respond to it!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="⌛ Confirmation timed out — no loans were deleted.", embed=None, view=None
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Delete Loans", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        count = len(self.loans)
        for loan in self.loans:
            await loan.delete()

        embed = discord.Embed(
            title="🗑️ Cleanup Complete",
            description=f"Deleted {count} paid loan(s) older than {self.cutoff_days} day(s).",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            content="Cleanup cancelled — no loans were deleted.", embed=None, view=None
        )


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

        # Check for existing unpaid loan between these users in this guild
        existing_loan = await Loan.get_or_none(
            lender=lender, borrower=borrower, is_paid=False, guild_id=interaction.guild.id
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
                guild_id=interaction.guild.id,
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

        loan = await Loan.get_or_none(id=loan_id, guild_id=interaction.guild.id).prefetch_related(
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

        await Transaction.create(
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

        loans_given = await Loan.filter(
            lender=user, is_paid=False, guild_id=interaction.guild.id
        ).prefetch_related("borrower")
        loans_received = await Loan.filter(
            borrower=user, is_paid=False, guild_id=interaction.guild.id
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
        loan = await Loan.get_or_none(id=loan_id, guild_id=interaction.guild.id).prefetch_related(
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

    @app_commands.command(name="allloans", description="List all loans on the server (Admin only)")
    @app_commands.describe(include_paid="Include loans that have already been paid off (default: False)")
    @app_commands.default_permissions(administrator=True)
    async def all_loans(self, interaction: discord.Interaction, include_paid: bool = False):
        """List all loans — admin only"""
        await interaction.response.defer(ephemeral=True)

        loans = await Loan.filter(guild_id=interaction.guild.id).prefetch_related("lender", "borrower")
        if not include_paid:
            loans = [loan for loan in loans if not loan.is_paid]

        config = await get_guild_config(interaction.guild.id)

        if not loans:
            status_note = "paid or unpaid" if include_paid else "unpaid"
            await interaction.followup.send(f"📭 No {status_note} loans found.", ephemeral=True)
            return

        total_outstanding = sum(loan.amount for loan in loans if not loan.is_paid)

        embed = discord.Embed(
            title="🗂️ All Loans" + (" (including paid)" if include_paid else ""),
            description=f"**{len(loans)}** loan(s) found"
            + (f" — Outstanding: {config.format_currency(float(total_outstanding))}" if total_outstanding else ""),
            color=discord.Color.dark_gold(),
            timestamp=datetime.now(timezone.utc),
        )

        # Discord embed field value limit is 1024 chars; batch loans into chunks
        chunk, chunk_lines = [], []
        for loan in loans:
            try:
                lender_user = await self.bot.fetch_user(loan.lender.discord_id)
                lender_str = lender_user.mention
            except discord.NotFound:
                lender_str = f"`{loan.lender.discord_id}`"
            try:
                borrower_user = await self.bot.fetch_user(loan.borrower.discord_id)
                borrower_str = borrower_user.mention
            except discord.NotFound:
                borrower_str = f"`{loan.borrower.discord_id}`"

            status = "✅" if loan.is_paid else "⏳"
            line = (
                f"{status} **#{loan.id}** {lender_str} → {borrower_str}: "
                f"{config.format_currency(float(loan.amount))} "
                f"*(created {loan.created_at.strftime('%Y-%m-%d')})*"
            )
            chunk_lines.append(line)

            # Flush chunk every 10 entries or when approaching field value limit
            if len(chunk_lines) == 10:
                embed.add_field(
                    name=f"Loans {len(chunk) * 10 + 1}–{len(chunk) * 10 + len(chunk_lines)}",
                    value="\n".join(chunk_lines),
                    inline=False,
                )
                chunk.append(chunk_lines)
                chunk_lines = []

        if chunk_lines:
            start = len(chunk) * 10 + 1
            end = start + len(chunk_lines) - 1
            embed.add_field(
                name=f"Loans {start}–{end}",
                value="\n".join(chunk_lines),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="markpaid", description="Mark a loan as fully paid")
    @app_commands.describe(loan_id="The ID of the loan to mark as paid")
    async def mark_paid(self, interaction: discord.Interaction, loan_id: int):
        """Mark a loan as fully paid"""
        loan = await Loan.get_or_none(id=loan_id, guild_id=interaction.guild.id).prefetch_related("lender", "borrower")

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

    @app_commands.command(name="deleteloan", description="Permanently delete a loan (Admin only)")
    @app_commands.describe(loan_id="The ID of the loan to delete")
    @app_commands.default_permissions(administrator=True)
    async def delete_loan(self, interaction: discord.Interaction, loan_id: int):
        """Permanently delete a loan and its transaction history — admin only"""
        loan = await Loan.get_or_none(id=loan_id, guild_id=interaction.guild.id).prefetch_related(
            "lender", "borrower"
        )

        if not loan:
            await interaction.response.send_message(f"❌ Loan #{loan_id} not found!", ephemeral=True)
            return

        try:
            lender_str = (await self.bot.fetch_user(loan.lender.discord_id)).mention
        except discord.NotFound:
            lender_str = f"`{loan.lender.discord_id}`"
        try:
            borrower_str = (await self.bot.fetch_user(loan.borrower.discord_id)).mention
        except discord.NotFound:
            borrower_str = f"`{loan.borrower.discord_id}`"

        config = await get_guild_config(interaction.guild.id)
        amount_str = config.format_currency(float(loan.amount))
        transaction_count = await Transaction.filter(loan=loan).count()

        embed = discord.Embed(
            title="⚠️ Confirm Loan Deletion",
            description=f"Are you sure you want to permanently delete loan #{loan.id}? This cannot be undone.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Lender", value=lender_str, inline=True)
        embed.add_field(name="Borrower", value=borrower_str, inline=True)
        embed.add_field(name="Amount", value=amount_str, inline=True)
        embed.add_field(
            name="Status", value="✅ Paid" if loan.is_paid else "⏳ Unpaid", inline=True
        )
        if transaction_count:
            embed.add_field(
                name="Payment Records",
                value=f"{transaction_count} record(s) will also be deleted",
                inline=True,
            )

        view = DeleteLoanConfirmView(loan, lender_str, borrower_str, amount_str, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @app_commands.command(name="cleanup", description="Delete paid loans older than a number of days (Admin only)")
    @app_commands.describe(days="Delete paid loans that were paid off more than this many days ago")
    @app_commands.default_permissions(administrator=True)
    async def cleanup(self, interaction: discord.Interaction, days: app_commands.Range[int, 1]):
        """Bulk-delete paid loans past a retention window — admin only"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        loans = await Loan.filter(
            guild_id=interaction.guild.id, is_paid=True, paid_at__lt=cutoff
        ).prefetch_related("lender", "borrower")

        if not loans:
            await interaction.response.send_message(
                f"📭 No paid loans older than {days} day(s) found.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⚠️ Confirm Cleanup",
            description=(
                f"**{len(loans)}** paid loan(s) older than {days} day(s) will be permanently deleted. "
                "This cannot be undone."
            ),
            color=discord.Color.orange(),
        )

        view = CleanupConfirmView(loans, days, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @app_commands.command(name="leaderboard", description="Rank users by number of loans lent (Admin only)")
    @app_commands.describe(days="Only count loans created within this many days")
    @app_commands.default_permissions(administrator=True)
    async def leaderboard(self, interaction: discord.Interaction, days: app_commands.Range[int, 1]):
        """Rank lenders by number of loans created in the last N days — admin only"""
        await interaction.response.defer(ephemeral=True)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        loans = await Loan.filter(
            guild_id=interaction.guild.id, created_at__gte=cutoff
        ).prefetch_related("lender")

        if not loans:
            await interaction.followup.send(
                f"📭 No loans lent in the last {days} day(s).", ephemeral=True
            )
            return

        counts: dict[int, int] = {}
        lenders: dict[int, User] = {}
        for loan in loans:
            lender_id = loan.lender.id
            counts[lender_id] = counts.get(lender_id, 0) + 1
            lenders[lender_id] = loan.lender

        ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for rank, (lender_id, count) in enumerate(ranked):
            lender = lenders[lender_id]
            try:
                name = (await self.bot.fetch_user(lender.discord_id)).mention
            except discord.NotFound:
                name = f"`{lender.discord_id}`"
            prefix = medals[rank] if rank < len(medals) else f"`#{rank + 1}`"
            lines.append(f"{prefix} {name} — {count} loan(s) lent")

        embed = discord.Embed(
            title="🏆 Lending Leaderboard",
            description=f"Loans lent in the last {days} day(s), most to least",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc),
        )

        # Discord embed field value limit is 1024 chars; batch entries into chunks
        for i in range(0, len(lines), 10):
            chunk = lines[i:i + 10]
            embed.add_field(
                name=f"Rank {i + 1}–{i + len(chunk)}",
                value="\n".join(chunk),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(LoanCommands(bot))
