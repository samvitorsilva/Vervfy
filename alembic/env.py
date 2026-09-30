from __future__ import annotations

import os

from alembic import context
from db import Base, DATABASE_URL, normalize_database_url

config = context.config
migration_url = (
    normalize_database_url(os.environ.get("MIGRATION_DATABASE_URL", "").strip()) or DATABASE_URL
)
config.set_main_option("sqlalchemy.url", migration_url)
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    context.configure(url=migration_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config, pool
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
