"""Search terms as literal text inside ILIKE.

A user typing "%" or "_" into a search box means those characters, not "match
anything": unescaped, "%" alone matched every row and a long run of them
makes Postgres work hard for nothing.
"""

LIKE_ESCAPE = "\\"


def contains(q: str) -> str:
    """An ILIKE pattern matching `q` anywhere; pair it with escape=LIKE_ESCAPE."""
    term = q.strip()
    for ch in (LIKE_ESCAPE, "%", "_"):
        term = term.replace(ch, LIKE_ESCAPE + ch)
    return f"%{term}%"
