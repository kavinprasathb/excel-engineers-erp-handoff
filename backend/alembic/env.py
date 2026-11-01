"""Alembic environment.

The connection string always comes from the app settings, never from
alembic.ini, so there is one source of truth. Tests point TEST_DATABASE_URL at
a scratch database and run this same chain — the schema under test is the
schema a deploy produces, which is what v2 never verified.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.config import get_settings
from app.models import Base
from app.models.types import StrEnumType

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Render `StrEnumType` columns as the VARCHAR they physically are.

    Left alone, autogenerate emits `app.models.types.StrEnumType(length=30)`:
    a module it never imports, and — worse — missing the `enum_class` argument
    the constructor requires. The generated migration then fails with a
    NameError before anyone finds out the call was malformed too.

    A migration describes the physical schema, and the physical schema here is
    a VARCHAR. Rendering it as one keeps migrations free of any dependency on
    application code, which also means an old migration cannot break when an
    enum is renamed.
    """
    if type_ == "type" and isinstance(obj, StrEnumType):
        return f"sa.String(length={obj.impl.length})"
    return False


def _url() -> str:
    # `alembic -x url=...` wins, so tests can retarget without env juggling.
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        render_item=_render_item,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_item=_render_item,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
