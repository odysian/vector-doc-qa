from logging.config import fileConfig

from alembic import context
from app.config import settings
from app.database import Base
from app.models.base import Chunk, Document  # noqa
from app.models.message import Message  # noqa
from app.models.user import User  # noqa
from sqlalchemy import engine_from_config, pool, text

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# Schema we own; all other schemas (auth, storage, rostra, etc.) are ignored during autogenerate.
# Prevents autogenerate from generating DROP TABLE for Supabase/other apps when run against shared DB.
APP_SCHEMA = target_metadata.schema


def include_object(object, name, type_, reflected, compare_to):
    """Restrict autogenerate to APP_SCHEMA only. Ignores auth, storage, rostra, etc."""
    if hasattr(object, "schema") and object.schema is not None and object.schema != APP_SCHEMA:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=target_metadata.schema,
        include_schemas=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode. Creates quaero schema if missing (same pattern as Rostra)."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=target_metadata.schema,
            include_schemas=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            connection.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {target_metadata.schema}")
            )
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
