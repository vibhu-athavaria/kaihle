import os
from logging.config import fileConfig

from alembic.operations import ops as alembic_ops
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

    Comment ops are NOT top-level entries in ``upgrade_ops.ops``: Alembic nests
    them inside a per-table ``ModifyTableOps``. A flat filter on the top-level
    list matches nothing, so we strip them from inside each ``ModifyTableOps``
    and then discard any ``ModifyTableOps`` left empty.
    """
    for directive in directives:
        _strip_table_comment_ops(directive.upgrade_ops, alembic_ops.DropTableCommentOp)
        _strip_table_comment_ops(directive.downgrade_ops, alembic_ops.CreateTableCommentOp)


def _strip_table_comment_ops(container: alembic_ops.OpContainer, comment_op: type) -> None:
    """Remove ``comment_op`` instances from the per-table ops nested in ``container``."""
    kept: list[alembic_ops.MigrateOperation] = []
    for op in container.ops:
        if isinstance(op, alembic_ops.ModifyTableOps):
            op.ops = [nested for nested in op.ops if not isinstance(nested, comment_op)]
            if not op.ops:
                continue
        elif isinstance(op, comment_op):
            continue
        kept.append(op)
    container.ops = kept


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
