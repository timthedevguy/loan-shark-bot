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

There is no automated test suite (no pytest, no CI). [`tests/`](tests) contains standalone manual verification scripts — run individually with e.g. `poetry run python tests/test_db.py` — that print pass/fail output rather than using assertions. They default `DATABASE_URL` to `sqlite://tests/db.sqlite3` (gitignored) so they never touch the real dev `db.sqlite3`, and always close the database connection in a `finally` block even on failure.

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
- [`cogs/loan_commands.py`](cogs/loan_commands.py) — all loan business logic: `/lend`, `/repay`, `/myloans`, `/loan`, `/allloans`, `/markpaid`, `/deleteloan`, `/cleanup`, `/leaderboard`. The `LoanCommands` cog holds a `get_or_create_user()` helper used by all commands.
- [`cogs/general_commands.py`](cogs/general_commands.py) — `/ping`, `/info`, `/setcurrency` (opens the `SetCurrencyModal`).

**Key behavior — loan consolidation**: `/lend` checks for an existing unpaid loan between the same lender/borrower pair *within the current guild*. If one exists, it adds the new amount to that loan rather than creating a new record.

**Guild isolation**: `Loan` rows carry a `guild_id`, and every command that reads or mutates a loan (`/lend`, `/repay`, `/myloans`, `/loan`, `/allloans`, `/markpaid`, `/deleteloan`, `/cleanup`, `/leaderboard`) filters by `interaction.guild.id`. A loan created in one server is invisible and inaccessible (even by numeric ID) from another.

**Destructive-command confirmation**: `/deleteloan` and `/cleanup` don't act immediately — they show a preview embed with `discord.ui.View` Confirm/Cancel buttons (`DeleteLoanConfirmView` / `CleanupConfirmView` in [`cogs/loan_commands.py`](cogs/loan_commands.py)). Both views restrict button interaction to the admin who invoked the command via `interaction_check()`, and auto-expire after 30s via `on_timeout()`.

**Slash command sync**: Commands are synced globally (not to a specific guild) in `setup_hook`. After adding or renaming commands, the sync happens automatically on next startup, but Discord can take up to an hour to propagate global changes. For faster testing during development, sync to a specific guild instead.

## Environment

Copy `.env.example` to `.env`. Required variable: `DISCORD_TOKEN`. Optional: `DATABASE_URL` (defaults to `sqlite://db.sqlite3`), `SENTRY_DSN`.
