import asyncio
import sys
import os
from logging.config import fileConfig

from dotenv import load_dotenv

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.db.metadata import metadata as target_metadata
import app.db.models


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path, override=True, verbose=True)
else:
    print(f".env file not found at {dotenv_path}, relying on environment variables.")

config = context.config

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL is not set in environment variables or .env file")

config.set_main_option("sqlalchemy.url", database_url)
print(f"Alembic configured to use database: {database_url[:15]}...")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

configure_opts = {
    "target_metadata": target_metadata,
    "render_as_batch": True,
    "compare_type": True,
    "compare_server_default": True,
    "include_schemas": True,
    "naming_convention": target_metadata.naming_convention,
}


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        **configure_opts,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        **configure_opts
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    print("Running migrations in offline mode...")
    run_migrations_offline()
else:
    print("Running migrations in online mode...")
    asyncio.run(run_migrations_online())