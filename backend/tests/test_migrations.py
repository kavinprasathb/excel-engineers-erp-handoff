"""The migration chain itself.

v2 had migrations but its tests built the schema with `create_all()`, so the
chain was never actually run until a deploy ran it. These three tests make
"the migrations work" a fact checked on every commit.
"""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, text

from alembic import command
from app.models import Base


def _cfg(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    cfg.cmd_opts = type("O", (), {"x": [f"url={url}"]})()
    return cfg


def test_chain_is_reversible(engine: Engine) -> None:
    """upgrade -> downgrade -> upgrade.

    Forces every migration to have a working downgrade(). Without this, a bad
    deploy can only be rolled forward, which during an incident is no rollback
    at all.
    """
    url = str(engine.url.render_as_string(hide_password=False))
    cfg = _cfg(url)
    command.downgrade(cfg, "base")

    with engine.connect() as conn:
        remaining = {
            r[0]
            for r in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        }
    assert remaining <= {"alembic_version"}, f"downgrade left tables behind: {remaining}"

    command.upgrade(cfg, "head")


def test_models_and_migrations_agree(engine: Engine) -> None:
    """No pending autogenerate diff.

    This is what makes "the models match the schema" checkable rather than
    hoped for. It only works reliably because Base.metadata carries a naming
    convention — without one, Alembic cannot match unnamed constraints and
    reports phantom differences forever.
    """
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)

    # Exactly one index cannot survive an autogenerate round-trip: a GIN index
    # over a concatenation expression, which Alembic re-proposes every run. It
    # is named explicitly rather than exempting "expression indexes" as a class,
    # so drift in any OTHER index still fails this test.
    UNCOMPARABLE = {"ix_products_search_trgm"}

    def is_known_uncomparable(entry: object) -> bool:
        if not (isinstance(entry, tuple) and len(entry) == 2):
            return False
        action, obj = entry
        if action not in {"add_index", "remove_index"}:
            return False
        return getattr(obj, "name", None) in UNCOMPARABLE

    real = [d for d in diff if not is_known_uncomparable(d)]
    assert not real, f"models and migrations disagree: {real}"


def test_settings_singleton_was_seeded(engine: Engine) -> None:
    """The migration inserts the row, so no application code needs a
    get-or-create path and no request can ever find settings missing."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, company_name, low_stock_threshold FROM app_settings")
        ).all()
    assert len(rows) == 1
    assert rows[0][0] == 1


def test_pg_trgm_is_installed_by_the_migration(engine: Engine) -> None:
    """The trigram indexes depend on it; autogenerate never emits the CREATE."""
    with engine.connect() as conn:
        found = conn.execute(
            text("SELECT count(*) FROM pg_extension WHERE extname = 'pg_trgm'")
        ).scalar()
    assert found == 1


@pytest.mark.parametrize(
    "constraint",
    [
        "ck_inventory_on_hand_non_negative",
        "ck_inventory_reserved_non_negative",
        "ck_inventory_reserved_within_on_hand",
        "ck_app_settings_singleton",
        "ck_stock_movements_movement_not_empty",
    ],
)
def test_invariants_exist_as_database_constraints(engine: Engine, constraint: str) -> None:
    """These are the app's promises about stock. They must live in the schema,
    where no code path — not even raw SQL — can go around them."""
    with engine.connect() as conn:
        found = conn.execute(
            text("SELECT count(*) FROM pg_constraint WHERE conname = :name"),
            {"name": constraint},
        ).scalar()
    assert found == 1, f"missing database constraint {constraint}"
