from __future__ import annotations

import os

from alembic import context
# Validate staging before importing db (which constructs an application engine).
if os.environ.get("VERVFY_ENVIRONMENT", "").strip().lower() == "staging":
    from staging_guard import validate
    validate()

from db import DATABASE_URL, Base, normalize_database_url

config = context.config
migration_url = (
    normalize_database_url(os.environ.get("MIGRATION_DATABASE_URL", "").strip()) or DATABASE_URL
)
config.set_main_option("sqlalchemy.url", migration_url.replace("%", "%%"))
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    context.configure(url=migration_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config, pool
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        if os.environ.get("VERVFY_ENVIRONMENT") == "staging":
            connection.exec_driver_sql("SET search_path TO public")
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
