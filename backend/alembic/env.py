import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context  # type: ignore[attr-defined]

# Import models so Alembic can detect them
from app.models import Base  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get DATABASE_URL from environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    # Replace the sqlalchemy.url in the config with the environment variable
    config.set_main_option("sqlalchemy.url", DATABASE_URL)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def include_object(object, name, type_, reflected, compare_to):  # type: ignore[override]
    """Skip reflected-only indexes from autogenerate.

    Indexes that exist in the DB with legacy idx_* names but have no ORM
    declaration are still correct — Alembic should not drop them.
    """
    if type_ == "index" and reflected and compare_to is None:
        return False
    return True


def process_revision_directives(context, revision, directives):  # type: ignore[override]
    """Strip table comment operations from autogenerate output.

    Table comments (COMMENT ON TABLE) are DB documentation only.
    Alembic has no ORM-side comment declarations, so every autogenerate
    run would emit drop_table_comment noise for every table. We suppress
    all of them here before the migration file is written.
    """
    from alembic.operations import ops as alembic_ops

    for directive in directives:
        directive.upgrade_ops.ops = [
            op for op in directive.upgrade_ops.ops if not isinstance(op, alembic_ops.DropTableCommentOp)
        ]
        directive.downgrade_ops.ops = [
            op for op in directive.downgrade_ops.ops if not isinstance(op, alembic_ops.CreateTableCommentOp)
        ]


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=process_revision_directives,
        compare_type=False,
        compare_server_default=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        process_revision_directives=process_revision_directives,
        compare_type=False,
        compare_server_default=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
