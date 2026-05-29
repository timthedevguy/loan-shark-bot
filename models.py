"""
Database models for the Loan Shark Bot using Tortoise ORM
"""
from tortoise import fields
from tortoise.models import Model
from datetime import datetime


class Config(Model):
    """Stores guild-specific configuration settings"""
    id = fields.IntField(pk=True)
    guild_id = fields.BigIntField(unique=True, index=True)
    currency_prefix = fields.CharField(max_length=10, default="$", null=True)
    currency_suffix = fields.CharField(max_length=10, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "config"

    def __str__(self):
        return f"Config(guild={self.guild_id})"

    def format_currency(self, amount: float) -> str:
        """Format an amount with the configured prefix/suffix"""
        formatted = f"{amount:,.2f}"
        if self.currency_prefix:
            formatted = f"{self.currency_prefix}{formatted}"
        if self.currency_suffix:
            formatted = f"{formatted}{self.currency_suffix}"
        return formatted


class User(Model):
    """Represents a Discord user in the system"""
    id = fields.IntField(pk=True)
    discord_id = fields.BigIntField(unique=True, index=True)
    username = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    
    # Relationships
    loans_given = fields.ReverseRelation["Loan"]
    loans_received = fields.ReverseRelation["Loan"]
    
    class Meta:
        table = "users"
    
    def __str__(self):
        return f"User({self.username} - {self.discord_id})"


class Loan(Model):
    """Represents a loan between two users"""
    id = fields.IntField(pk=True)
    lender = fields.ForeignKeyField("models.User", related_name="loans_given")
    borrower = fields.ForeignKeyField("models.User", related_name="loans_received")
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    description = fields.TextField(null=True)
    is_paid = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    paid_at = fields.DatetimeField(null=True)
    due_date = fields.DatetimeField(null=True)
    
    class Meta:
        table = "loans"
    
    def __str__(self):
        status = "Paid" if self.is_paid else "Unpaid"
        return f"Loan(${self.amount} - {status})"


class Transaction(Model):
    """Represents a payment transaction for a loan"""
    id = fields.IntField(pk=True)
    loan = fields.ForeignKeyField("models.Loan", related_name="transactions")
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    note = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "transactions"
    
    def __str__(self):
        return f"Transaction(${self.amount} on {self.created_at})"

