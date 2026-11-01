"""Custom column types.

`StrEnumType` exists because a plain `String` column annotated
`Mapped[SomeStrEnum]` is a lie: SQLAlchemy stores the value fine, but what
comes back from the database is an ordinary `str`.

Most of the time that is harmless — `StrEnum` compares and hashes as a string,
so `row.status == Status.RUNNING` and `row.status in {Status.RUNNING}` both
work. It stops being harmless the moment an enum grows behaviour. This
codebase already has `ImportJobStatus.is_terminal`, and
`job.status.is_terminal` on a loaded row would raise `AttributeError` — at
runtime, in the import poller, not in any type check.

So the coercion happens once, here, rather than being remembered at every call
site.
"""

from enum import StrEnum
from typing import Any

from sqlalchemy import Dialect, String, TypeDecorator


class StrEnumType(TypeDecorator[Any]):
    """A VARCHAR column that always hands back real enum members.

    Deliberately not `sqlalchemy.Enum`: that creates a Postgres ENUM type,
    and adding a value to a native ENUM needs a migration and cannot be done
    inside a transaction on older servers. A VARCHAR plus this decorator keeps
    the schema boring and the Python side honest.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_class: type[StrEnum], length: int = 30) -> None:
        self.enum_class = enum_class
        super().__init__(length=length)

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        # Accept a bare string so seeds and raw inserts still work, but
        # validate it: an unknown value would otherwise reach the database and
        # only fail on the way back out.
        return self.enum_class(value).value

    def process_result_value(self, value: Any, dialect: Dialect) -> StrEnum | None:
        if value is None:
            return None
        return self.enum_class(value)
