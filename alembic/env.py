from __future__ import annotations

import os

from alembic import context

# A local profile is prohibited even when the general environment selector is absent or mis-set.
if os.environ.get("VERVFY_STAGING_PROFILE") == "local-disposable":
    from staging_guard import require_alembic_execution_enabled
    require_alembic_execution_enabled()

# Validate staging before importing db (which constructs an application engine).
if os.environ.get("VERVFY_ENVIRONMENT", "").strip().lower() == "staging":
    from staging_guard import require_alembic_execution_enabled, validate
    validate(operation="upgrade")
    require_alembic_execution_enabled()

from db import DATABASE_URL, Base, normalize_database_url

config = context.config
production_runner = config.attributes.get("vervfy_production_migration_runner") is True
production_connection = config.attributes.get("connection")
if os.environ.get("VERVFY_ENVIRONMENT", "").strip().lower() == "production" and (
    not production_runner or production_connection is None or context.is_offline_mode()
):
    raise RuntimeError(
        "Production Alembic execution is restricted to the production migration runner"
    )

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

    def run(connection) -> None:
        if os.environ.get("VERVFY_ENVIRONMENT") == "staging":
            connection.exec_driver_sql("SET search_path TO public")
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    if production_connection is not None:
        run(production_connection)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        run(connection)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
