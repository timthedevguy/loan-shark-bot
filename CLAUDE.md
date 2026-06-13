# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the bot
poetry run python start_shark.py

# Lint
poetry run ruff check .

# Fix lint issues
poetry run ruff check . --fix

# Install dependencies
poetry install
```

There are no automated tests in this project.

## Architecture

**Entry point**: [`start_shark.py`](start_shark.py) creates the `discord.commands.Bot` instance, wires up global error handlers, calls `init_db()` in `setup_hook`, loads all cogs, then syncs slash commands to Discord.

**Database layer**: [`database.py`](database.py) initializes Tortoise ORM against `DATABASE_URL` (defaults to `sqlite://db.sqlite3`) and calls `generate_schemas()` on every startup — there are no migration files; schema changes apply automatically on next run.

**Models** ([`models.py`](models.py)):
- `Config` — per-guild currency formatting (prefix/suffix). Also owns the `format_currency()` helper method.
- `User` — maps Discord user IDs to internal records; lazily created on first interaction.
- `Loan` — core entity: links lender + borrower `User` records within a `guild_id`, tracks `amount`, `is_paid`, and `paid_at`.
- `Transaction` — individual repayment records attached to a `Loan`.

**Utilities** ([`utils.py`](utils.py)): `get_guild_config()` does a `get_or_create` for a guild's `Config` row. Commands call this to get a `Config` object and then call `config.format_currency()` directly.

**Cogs**:
- [`cogs/loan_commands.py`](cogs/loan_commands.py) — all loan business logic: `/lend`, `/repay`, `/myloans`, `/loan`, `/allloans`, `/markpaid`, `/setcurrency`. The `LoanCommands` cog holds a `get_or_create_user()` helper used by all commands.
- [`cogs/general_commands.py`](cogs/general_commands.py) — `/ping`, `/info`.

**Key behavior — loan consolidation**: `/lend` checks for an existing unpaid loan between the same lender/borrower pair. If one exists, it adds the new amount to that loan rather than creating a new record.

**Slash command sync**: Commands are synced globally (not to a specific guild) in `setup_hook`. After adding or renaming commands, the sync happens automatically on next startup, but Discord can take up to an hour to propagate global changes. For faster testing during development, sync to a specific guild instead.

## Environment

Copy `.env.example` to `.env`. Required variable: `DISCORD_TOKEN`. Optional: `DATABASE_URL` (defaults to `sqlite://db.sqlite3`), `SENTRY_DSN`.
