from logging.config import fileConfig

from collections.abc import MutableMapping
from typing import Literal

from alembic import context
from alembic.runtime.migration import MigrationContext
from app.config import settings
from app.database import Base
from app.models.base import Chunk, Document  # noqa
from app.models.message import Message  # noqa
from app.models.user import User  # noqa
from sqlalchemy import Column, engine_from_config, pool, text
from sqlalchemy.schema import SchemaItem
from sqlalchemy.types import TypeEngine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Schema reflection contract
# ---------------------------------------------------------------------------
# All app tables live in the "quaero" schema.  The application DATABASE_URL
# sets search_path=quaero, making default_schema_name="quaero".  Alembic
# replaces the default schema with None internally, so reflected quaero
# tables arrive as schema=None while our models declare schema='quaero'
# explicitly.  This mismatch causes false-positive diffs:
#
#   1. FK churn — remove FK(users.id) + add FK(quaero.users.id) on every
#      table with foreign keys, even though nothing changed on disk.
#   2. ENUM type diffs — reflected PG ENUMs have schema='quaero' but model
#      Enums have no schema qualifier.
#   3. DROP TABLE alembic_version — reflected as schema=None, not in any
#      model, so autogenerate proposes removing it.
#
# Fix: the migration engine overrides search_path to "public" so that
# default_schema_name="public" and quaero tables are reflected with their
# explicit schema='quaero', matching model metadata exactly.  Combined with:
#   a) include_name — only reflect the quaero schema.
#   b) include_object — reject non-quaero objects and infrastructure tables.
#   c) compare_type — suppress schema-qualified ENUM false positives.
# ---------------------------------------------------------------------------

APP_SCHEMA = target_metadata.schema  # "quaero"

# Names of tables managed by Alembic/infrastructure, not app models.
_INFRASTRUCTURE_TABLES = frozenset({"alembic_version"})


def include_name(
    name: str | None,
    type_: Literal["schema", "table", "column", "index", "unique_constraint", "foreign_key_constraint"],
    parent_names: MutableMapping[
        Literal["schema_name", "table_name", "schema_qualified_table_name"],
        str | None,
    ],
) -> bool:
    """Control which schema names Alembic reflects during autogenerate.

    Only allow APP_SCHEMA so that public-schema objects (extension tables,
    other apps' tables) are never loaded into the reflected metadata.
    With search_path=public on the migration connection, the default schema
    is "public" (passed as None), so blocking None filters out public objects.
    """
    if type_ == "schema":
        return name == APP_SCHEMA
    return True


def compare_type(
    context: MigrationContext,
    inspected_column: Column[object],
    metadata_column: Column[object],
    inspected_type: TypeEngine[object],
    metadata_type: TypeEngine[object],
) -> bool | None:
    """Suppress false-positive type diffs caused by schema qualification.

    When search_path=public, PostgreSQL reflects ENUMs with schema='quaero'
    but the model Enum has no schema.  The underlying type is identical;
    only the schema qualifier differs.  Return False to suppress the diff.
    """
    from sqlalchemy import Enum as SAEnum
    from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

    if isinstance(inspected_type, PG_ENUM) and isinstance(metadata_type, SAEnum):
        # Compare by enum name and values, ignoring schema qualifier.
        if (
            getattr(inspected_type, "name", None) == getattr(metadata_type, "name", None)
            and getattr(inspected_type, "enums", None) == getattr(metadata_type, "enums", None)
        ):
            return False

    # Return None to let Alembic's default comparison handle it.
    return None


def include_object(
    object: SchemaItem,
    name: str | None,
    type_: Literal["schema", "table", "column", "index", "unique_constraint", "foreign_key_constraint"],
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    """Restrict autogenerate to APP_SCHEMA objects only.

    Rejects:
    - Tables/objects with an explicit schema that isn't APP_SCHEMA
    - Infrastructure tables (alembic_version) that are not app models
    """
    # Reject objects from non-app explicit schemas.
    schema = getattr(object, "schema", None)
    if schema is not None and schema != APP_SCHEMA:
        return False

    # Reject infrastructure tables that aren't app models.
    if type_ == "table" and reflected and name in _INFRASTRUCTURE_TABLES:
        return False

    return True


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

# Shared context.configure kwargs for both online and offline modes.
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well.  By skipping the Engine creation we
    don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    context.configure(
        url=settings.database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        target_metadata=target_metadata,
        version_table_schema=APP_SCHEMA,
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
        compare_type=compare_type,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode. Creates quaero schema if missing.

    The engine is created with search_path=public so that the dialect's
    default_schema_name is "public", not "quaero".  This is critical for
    autogenerate: with include_schemas=True, Alembic replaces the default
    schema with None internally.  If default_schema_name were "quaero",
    reflected tables would arrive as schema=None while our models declare
    schema='quaero', causing false-positive FK diffs.  With
    default_schema_name="public", quaero tables are reflected with their
    explicit schema='quaero', matching model metadata exactly.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Force search_path=public so default_schema_name != APP_SCHEMA.
        # Without this, if DATABASE_URL sets search_path=quaero (as ours
        # does), reflected quaero tables get schema=None and autogenerate
        # sees phantom FK diffs.
        connect_args={"options": "-csearch_path=public"},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=APP_SCHEMA,
            include_schemas=True,
            include_name=include_name,
            include_object=include_object,
            compare_type=compare_type,
        )

        with context.begin_transaction():
            connection.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {APP_SCHEMA}")
            )
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
