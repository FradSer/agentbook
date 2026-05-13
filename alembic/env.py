from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from backend.core.config import settings
from backend.infrastructure.persistence.sqlalchemy_models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if settings.database_url:
    config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # ``transaction_per_migration=True`` is the only mode in which
        # Alembic honours ``disable_ddl_transaction = True`` on individual
        # migration scripts. Without it the outer ``begin_transaction()``
        # below wraps every migration, and Postgres refuses
        # ``CREATE INDEX CONCURRENTLY`` inside a transaction block (see
        # ``c7bae2af560d`` and ``n9o0p1q2r3s4``). With it, each migration
        # gets its own transaction unless the script opts out via
        # ``disable_ddl_transaction``.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
