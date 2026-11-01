"""Test fixtures.

Two rules this file exists to enforce:

1. **Real Postgres, never SQLite.** The generated column, the CHECK
   constraints, FOR UPDATE and the trigram indexes are all Postgres features.
   Testing against SQLite would test a different database from the one that
   runs in production — which is how v2 shipped a migration chain nobody had
   ever run.
2. **The schema is built by the actual migration chain**, not `create_all()`.
   If a migration is wrong, every test fails, immediately.
"""

import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.config import get_settings
from app.services.stock import install_stock_guard

# The suite is not production, wherever it runs (CI sets no ENVIRONMENT, and
# the default is production). Set before app.main builds the app.
os.environ.setdefault("ENVIRONMENT", "test")
get_settings.cache_clear()

_testclient_init = TestClient.__init__


def _same_origin_testclient_init(self: TestClient, *args: object, **kwargs: object) -> None:
    """Every test client speaks as the SPA does: with its own Origin.

    The CSRF check refuses a mutating request that names no origin at all, as
    a browser's fetch always does. Tests of that refusal drop the header.
    """
    _testclient_init(self, *args, **kwargs)  # type: ignore[arg-type]
    self.headers.setdefault("Origin", str(self.base_url).rstrip("/"))


TestClient.__init__ = _same_origin_testclient_init  # type: ignore[method-assign]


def _base_test_url() -> str:
    url = get_settings().test_database_url
    # A guard, not a formality: this suite destroys whatever it points at.
    # Pointing it at the live database would be unrecoverable.
    if not url.rsplit("/", 1)[-1].endswith("_test"):
        raise RuntimeError(f"TEST_DATABASE_URL must name a database ending in '_test'; got {url!r}")
    return url


def _run_url(base: str, suffix: str) -> str:
    head, _, name = base.rpartition("/")
    return f"{head}/{name}_{suffix}"


def _process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _drop_abandoned_databases(conn: Connection, *, keep: str) -> None:
    """Delete test databases left behind by runs that were killed.

    The per-process database is dropped in this fixture's teardown, which never
    happens if pytest is killed — by a timeout, by Ctrl-C, or by the OOM killer.
    Six of these had accumulated on the server before this existed, one of them
    still holding a transaction open fifty minutes after its process died.
    Nothing cleaned them up, because nothing was looking.

    Only databases whose owning process is gone are dropped, so a concurrent
    run on this machine is safe. The names carry a *local* pid, so a second
    developer's database could look abandoned from here — which is why this
    also requires the database to have no connections at all. Both conditions,
    never either.
    """
    stale = [
        name
        for (name,) in conn.execute(
            text("SELECT datname FROM pg_database WHERE datname LIKE :pattern"),
            {"pattern": f"{keep.rsplit('_', 1)[0]}_%"},
        )
        if name != keep
    ]
    for name in stale:
        suffix = name.rsplit("_", 1)[-1]
        if not suffix.isdigit() or _process_is_alive(int(suffix)):
            continue
        in_use = conn.execute(
            text("SELECT count(*) FROM pg_stat_activity WHERE datname = :name"),
            {"name": name},
        ).scalar_one()
        if in_use:
            continue
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """A database of this run's very own, built by the real migration chain.

    Per-process rather than one shared `excel_test`, because a shared one does
    not survive concurrency: two pytest processes both issuing
    `DROP SCHEMA public CASCADE` deadlock each other, and the failure surfaces
    as an unrelated-looking SQLAlchemy error at fixture setup. That happened as
    soon as two agents worked on the backend at once, and it would happen again
    under pytest-xdist or two terminals.

    The cost is one CREATE DATABASE per run; the migration chain has to run
    either way.
    """
    base = _base_test_url()
    url = _run_url(base, str(os.getpid()))
    db_name = url.rsplit("/", 1)[-1]

    # CREATE DATABASE cannot run inside a transaction, and cannot run while
    # connected to the database being created — hence the maintenance database.
    maintenance = create_engine(base.rsplit("/", 1)[0] + "/postgres", isolation_level="AUTOCOMMIT")
    with maintenance.connect() as conn:
        _drop_abandoned_databases(conn, keep=db_name)
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    cfg.cmd_opts = type("O", (), {"x": [f"url={url}"]})()  # mimic `alembic -x url=...`
    command.upgrade(cfg, "head")

    eng = create_engine(url)
    try:
        yield eng
    finally:
        eng.dispose()
        with maintenance.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        maintenance.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """One transaction per test, rolled back afterwards.

    Fast and fully isolated: no test can see another's rows, and nothing is
    left behind even when a test fails mid-way.
    """
    conn = engine.connect()
    txn = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    install_stock_guard(session)
    try:
        yield session
    finally:
        session.close()
        txn.rollback()
        conn.close()


@pytest.fixture(autouse=True)
def _require_env() -> None:
    if "TEST_DATABASE_URL" not in os.environ and not get_settings().test_database_url:
        pytest.skip("TEST_DATABASE_URL not configured")
