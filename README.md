# Loan Shark Bot 🦈

A Discord bot for managing loans between server members using Discord.py, SQLite, and Tortoise ORM.

## Features

- 💰 **Create Loans**: Lend money to other server members
- 🔄 **Automatic Consolidation**: Multiple loans to the same person are automatically combined
- 💵 **Track Repayments**: Record partial or full loan repayments
- 📊 **View Loans**: See all your active loans (given and received)
- 📋 **Loan Details**: View detailed information about specific loans including payment history
- ✅ **Mark as Paid**: Lenders can mark loans as fully paid
- 💱 **Custom Currency**: Set server-specific currency symbols and formats

## Setup

### Prerequisites

- Python 3.12 or higher
- Poetry (for dependency management)
- A Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))

### Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd loan_shark_bot
```

2. Install dependencies with Poetry:

```bash
poetry install
```

3. Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

4. Edit the `.env` file and add your Discord bot token:

```env
DISCORD_TOKEN=your_discord_bot_token_here
DATABASE_URL=sqlite://db.sqlite3
```

### Getting a Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Under the bot's username, click "Reset Token" to get your token
5. Copy the token to your `.env` file
6. Enable these Privileged Gateway Intents:
    - Message Content Intent
    - Server Members Intent
7. Go to OAuth2 > URL Generator
8. Select scopes: `bot`
9. Select bot permissions: `Send Messages`, `Read Messages/View Channels`, `Use Slash Commands`
10. Use the generated URL to invite the bot to your server

## Running the Bot

Start the bot with:

```bash
poetry run python start_shark.py
```

Or activate the virtual environment first:

```bash
poetry shell
python start_shark.py
```

## Available Commands

All commands use Discord's slash command interface (`/command`). All responses are private (only visible to you).

### General Commands

- `/ping` - Check bot latency
- `/info` - Show bot information

### Loan Commands

- `/lend member:<@user> amount:<amount> [description:<text>]`
    - Create a new loan
    - Example: `/lend member:@JohnDoe amount:100 description:Pizza money`
    - This creates a $100 loan
    - **Note**: If you already have an unpaid loan with this person, the new amount will be added to the existing loan
      instead of creating a separate one
    - **Privacy**: Response only visible to you

- `/repay loan_id:<id> amount:<amount> [note:<text>]`
    - Record a repayment on a loan (available to both the borrower and lender)
    - Example: `/repay loan_id:1 amount:50 note:First payment`
    - Automatically marks the loan as paid if total payments meet or exceed the loan amount
    - **Privacy**: Response only visible to you

- `/myloans`
    - View all your active loans (both given and received)
    - Each person appears only once, showing the total amount owed
    - **Privacy**: Response only visible to you

- `/loan loan_id:<id>`
    - View detailed information about a specific loan
    - Example: `/loan loan_id:1`
    - **Privacy**: Response only visible to you

- `/markpaid loan_id:<id>`
    - Mark a loan as fully paid (lender only)
    - Example: `/markpaid loan_id:1`
    - **Privacy**: Response only visible to you

- `/deleteloan loan_id:<id>`
    - Permanently delete a loan and its payment history (Admin only)
    - Example: `/deleteloan loan_id:1`
    - Shows a confirmation prompt (Delete/Cancel buttons) before anything is deleted
    - **Privacy**: Response only visible to you

- `/cleanup days:<number>`
    - Permanently delete all paid loans that were paid off more than `days` days ago (Admin only)
    - Example: `/cleanup days:90` deletes paid loans with a `paid_at` older than 90 days
    - `days` is required and must be at least 1
    - Shows a confirmation prompt with the number of loans that will be deleted before anything is deleted
    - **Privacy**: Response only visible to you

- `/leaderboard days:<number>`
    - Rank users by number of loans lent within the last `days` days, most to least (Admin only)
    - Example: `/leaderboard days:30` ranks lenders by loans created in the last 30 days
    - `days` is required and must be at least 1
    - Counts loans by creation date regardless of paid/unpaid status
    - **Privacy**: Response only visible to you

### Currency Commands

- `/setcurrency`
    - Opens a modal dialog to set custom currency format for your server (Admin only)
    - The modal has two fields:
        - **Prefix**: Symbol or text before the amount (e.g. `$`, `€`, `£`)
        - **Suffix**: Text after the amount (e.g. `ISK`, `USD`, `coins`). A space is automatically added before the
          suffix.
    - Example result with prefix `€`: `€100.00`
    - Example result with prefix `$` and suffix `USD`: `$100.00 USD`
    - **Privacy**: Response only visible to you

## How Loan Consolidation Works

When you lend money to someone who already owes you money (unpaid loan), the bot automatically combines the loans:

**Example:**

1. `/lend member:@Bob amount:100 description:Dinner` → Creates loan #1 for $100
2. `/lend member:@Bob amount:50 description:Movie tickets` → Adds $50 to loan #1 (now $150 total)
3. `/myloans` → Shows Bob once with $150 owed

**Benefits:**

- Cleaner loan list - each person appears only once
- Easier to track total amount per person
- Automatic consolidation - no extra commands needed

**After Payoff:**

- Once a loan is marked as paid, future loans start fresh
- Loan history is preserved in the database

## Database

The bot uses SQLite with Tortoise ORM for data persistence. The database file (`db.sqlite3`) is automatically created
when you first run the bot.

### Database Models

- **Config**: Guild-specific configuration (currency prefix/suffix per server)
- **User**: Discord users who participate in loans
- **Loan**: Loan records with amount and status
- **Transaction**: Payment transactions for loans

## Project Structure

```
loan_shark_bot/
├── start_shark.py          # Main bot entry point
├── database.py             # Database initialization
├── models.py               # Tortoise ORM models
├── utils.py                # Utility functions (currency formatting, etc.)
├── cogs/
│   ├── loan_commands.py    # Loan management commands
│   └── general_commands.py # General utility commands
├── .env                    # Environment variables (not in git)
├── .env.example            # Example environment file
├── pyproject.toml          # Project dependencies
└── README.md               # This file
```

## Error Monitoring

The bot includes optional Sentry integration for error monitoring. To enable it, add your Sentry DSN to the `.env` file:

```env
SENTRY_DSN=your_sentry_dsn_here
```

## Development

### Adding New Commands

1. Create a new command in an existing cog or create a new cog file in the `cogs/` directory
2. Use the `@app_commands.command()` decorator for slash commands
3. Add the cog to the load list in `start_shark.py` if it's a new cog

Example:

```python
@app_commands.command(name="mycommand", description="Description of my command")
async def my_command(self, interaction: discord.Interaction, arg1: str):
    await interaction.response.send_message(f"You said: {arg1}", ephemeral=True)
```

### Database Migrations

If you modify the models, Tortoise ORM will automatically update the schema on next run. For production, consider using
Aerich for proper migrations.

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you encounter any issues or have questions, please open an issue on GitHub.

