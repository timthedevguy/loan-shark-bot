"""
Database initialization and configuration for Tortoise ORM
"""
import os
from tortoise import Tortoise


async def init_db():
    """Initialize the database connection"""
    database_url = os.getenv("DATABASE_URL", "sqlite://db.sqlite3")
    
    await Tortoise.init(
        db_url=database_url,
        modules={"models": ["models"]}
    )
    
    # Generate schemas
    await Tortoise.generate_schemas()
    print("Database initialized successfully!")


async def close_db():
    """Close the database connections"""
    await Tortoise.close_connections()
    print("Database connections closed.")

