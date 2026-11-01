"""Whether the person being served may see purchase cost.

Set per request by `viewer.track`; read by the schemas when they serialise.
Defaults to hidden, so anything that forgets to set it fails closed.
"""

from contextvars import ContextVar

_can_see_cost: ContextVar[bool] = ContextVar("can_see_cost", default=False)


def can_see_cost() -> bool:
    return _can_see_cost.get()


def set_can_see_cost(value: bool) -> None:
    _can_see_cost.set(value)
