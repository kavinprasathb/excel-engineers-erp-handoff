"""Architecture rules, enforced by walking the source rather than by review.

The session guard in `stock.py` catches a bypass at runtime, but only if a test
exercises that code path. This catches it statically, so an unexercised route
handler cannot smuggle a direct write into production.
"""

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parent.parent / "app"

COUNTER_COLUMNS = {"quantity_on_hand", "quantity_reserved", "quantity_available"}
STOCK_SERVICE = APP / "services" / "stock.py"


def _python_files() -> list[pathlib.Path]:
    return [p for p in APP.rglob("*.py") if "__pycache__" not in p.parts]


def test_only_the_stock_service_assigns_to_stock_counters() -> None:
    """`inv.quantity_on_hand = ...` outside stock.py is a bug, not a style choice.

    This is the rule that v2 lacked. There, the invariant lived in one function
    and the fulfilment code simply did not call it, so the ledger and the
    counters drifted apart with nothing to notice.
    """
    offenders: list[str] = []

    for path in _python_files():
        if path == STOCK_SERVICE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, ast.AugAssign | ast.AnnAssign):
                targets = [node.target]

            for target in targets:
                # Only attribute assignment on an instance counts. A model file
                # *declaring* the column is a plain Name, not an Attribute.
                if isinstance(target, ast.Attribute) and target.attr in COUNTER_COLUMNS:
                    rel = path.relative_to(APP.parent)
                    offenders.append(f"{rel}:{node.lineno} writes .{target.attr}")

    assert not offenders, (
        "Stock counters may only be written by app/services/stock.py.\n"
        "Use adjust/receive/reserve/release/deliver instead, so the ledger "
        "always explains the numbers.\nOffending lines:\n  " + "\n  ".join(offenders)
    )


def test_no_raw_sql_built_by_string_formatting() -> None:
    """SQL must be parameterised. An f-string into text() is an injection waiting to happen."""
    offenders: list[str] = []

    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "text" or not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.JoinedStr) or (
                isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod)
            ):
                rel = path.relative_to(APP.parent)
                offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "text() must receive a literal with bound parameters, never an f-string "
        "or %-format.\nOffending lines:\n  " + "\n  ".join(offenders)
    )


def test_stock_service_never_commits() -> None:
    """The caller owns the transaction.

    If the service committed, an order's status change and its stock
    reservation could land in separate transactions — and a crash between them
    would leave stock reserved for an order that does not exist.
    """
    tree = ast.parse(STOCK_SERVICE.read_text(encoding="utf-8"), filename=str(STOCK_SERVICE))
    commits = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "commit"
    ]
    assert not commits, f"stock.py must not commit; found calls at lines {commits}"
