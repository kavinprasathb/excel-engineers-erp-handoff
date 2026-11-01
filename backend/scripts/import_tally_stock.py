"""Import a Tally "Stock Summary" export into Products and Inventory.

Run from the backend folder:

    uv run python -m scripts.import_tally_stock "StkSum 5TH Oct.xlsx" --preview out.xlsx
    uv run python -m scripts.import_tally_stock "StkSum 5TH Oct.xlsx" --apply

How the sheet is read:

* A row with no quantity is a Tally stock group: it becomes the category.
* Inside a group, Tally repeats each sub-group ("Spares for CPK", "Ball
  Valve"...) as a row carrying the total of the items under it. Those rows
  are found by their sums (a row whose quantity and value equal the rows
  after it), not by indentation, which the export does not keep reliably.
  Three sub-groups do not add up exactly in Tally and are named in
  KNOWN_SUBGROUPS. Sub-group rows are never imported, so nothing is counted
  twice; the sub-group is kept in each item's description.
* The Service group and any "Service Charge..." row are charges, not stock,
  and are left out.

What each item becomes: a product named exactly as in Tally, a generated SKU
per group (STD-0001...), purchase cost = Tally's rate, GST 18%, selling
price 0 and HSN blank (to be filled in), a supplier only where the brand is
certain (BRANDS), and its closing quantity booked as an "Opening stock"
receipt through the stock service, so the ledger explains every unit.

--apply skips any product whose name already exists, so it is safe to rerun.
Brand suppliers that do not exist are created without GST/address and show
as "Needs details" until completed in Suppliers.
"""

import argparse
import functools
import re
import sys
from typing import Any

from openpyxl import Workbook, load_workbook  # type: ignore[import-untyped]
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Category, Product, Supplier, User
from app.schemas.category import CategoryCreate
from app.schemas.product import ProductCreate
from app.services import categories, products

SKIP_GROUPS = {"Service"}
# Sub-group rows whose Tally totals do not match their items exactly.
KNOWN_SUBGROUPS = {"Spares for Etanorm SYT", "ETN SYT WS 25 LS", "Spares for WK/WKS/WL"}
SKU_PREFIX = {
    "STD SPARES": "STD",
    "Valves": "VLV",
    "Pump": "PMP",
    "Accessories": "ACC",
    "Motor": "MTR",
    "Non Standered Spares": "NSS",
}
# Brand written in the item name.
NAME_BRANDS = [
    ("lovejoy", "Lovejoy"),
    ("ksb", "KSB"),
    ("crompton", "Crompton"),
    ("siemens", "Siemens"),
    ("skf", "SKF"),
]
# KSB product ranges, matched against the sub-group or the start of the name.
KSB_RANGES = re.compile(
    r"^(spares for )?(etanorm|etn|etny|etabloc|megachem|mega|mcpk|cpk|movi|movitec|kwp|hda|hgc|"
    r"wk|wks|wl|wkfi|ws \d+)\b",
    re.IGNORECASE,
)


def read(path: str) -> list[dict[str, Any]]:
    """The stock items of the sheet, sub-group totals and charges removed."""
    ws = load_workbook(path, data_only=True)["Stock Summary"]
    rows: list[dict[str, Any]] = []
    group = None
    for r in range(1, ws.max_row + 1):
        name, qty, rate, value = (ws.cell(r, i).value for i in range(1, 5))
        if name is None or str(name).strip() in ("", "Particulars", "Grand Total"):
            continue
        if r <= 11:  # letterhead and column headings
            continue
        if qty is None:
            group = str(name).strip()
            continue
        rows.append(
            {
                "row": r,
                "name": " ".join(str(name).split()),
                "qty": qty,
                "rate": rate or 0,
                "value": round(value or 0, 2),
                "group": group,
            }
        )
    n = len(rows)
    sys.setrecursionlimit(10_000)

    @functools.lru_cache(None)
    def span(i: int) -> tuple[int, bool]:
        """(where this row's block ends, is it a sub-group total)."""
        x = rows[i]
        if x["name"] in KNOWN_SUBGROUPS:
            j = i + 1
            while (
                j < n
                and rows[j]["group"] == x["group"]
                and not rows[j]["name"].startswith("Spares for")
            ):
                j = span(j)[0]
            return j, True
        sq, sv, j = 0, 0.0, i + 1
        while j < n and rows[j]["group"] == x["group"]:
            sq += rows[j]["qty"]
            sv += rows[j]["value"]
            j = span(j)[0]
            if sq == x["qty"] and abs(sv - x["value"]) < 1:
                return j, True
            if x["value"] >= 0 and sv > x["value"] + 1:
                break
        return i + 1, False

    items: list[dict[str, Any]] = []

    def walk(i: int, end: int, sub: str) -> None:
        while i < end:
            e, is_sub = span(i)
            if is_sub:
                walk(i + 1, e, rows[i]["name"])
            else:
                items.append({**rows[i], "subgroup": sub})
            i = e

    walk(0, n, "")
    return [
        x
        for x in items
        if x["group"] not in SKIP_GROUPS and not x["name"].lower().startswith("service charge")
    ]


def brand(item: dict[str, Any]) -> tuple[str, str]:
    """(supplier, why) or ("", "") when not certain."""
    low = item["name"].lower()
    for word, name in NAME_BRANDS:
        if word in low:
            return name, "name"
    if KSB_RANGES.match(item["subgroup"]) or KSB_RANGES.match(item["name"]):
        return "KSB", "KSB range"
    return "", ""


def plan(path: str) -> list[dict[str, Any]]:
    items = read(path)
    counters: dict[str, int] = {}
    for x in items:
        prefix = SKU_PREFIX.get(x["group"], "GEN")
        counters[prefix] = counters.get(prefix, 0) + 1
        x["sku"] = f"{prefix}-{counters[prefix]:04d}"
        x["supplier"], x["brand_by"] = brand(x)
    return items


def preview(items: list[dict[str, Any]], out: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Import preview"
    ws.append(
        [
            "Tally row",
            "SKU",
            "Name",
            "Category",
            "Sub-group (description)",
            "Opening qty",
            "Purchase cost (Rs.)",
            "Value (Rs.)",
            "Selling price",
            "HSN",
            "GST %",
            "Supplier",
            "Supplier set by",
        ]
    )
    for x in items:
        ws.append(
            [
                x["row"],
                x["sku"],
                x["name"],
                x["group"],
                x["subgroup"],
                x["qty"],
                x["rate"],
                x["value"],
                0,
                "",
                18,
                x["supplier"] or None,
                x["brand_by"] or None,
            ]
        )
    for col, w in zip(
        "ABCDEFGHIJKLM", [9, 10, 48, 20, 40, 11, 16, 14, 12, 8, 7, 12, 14], strict=True
    ):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "C2"
    wb.save(out)


def apply(items: list[dict[str, Any]]) -> None:
    db = SessionLocal()
    try:
        actor = db.execute(select(User.id).order_by(User.id)).scalars().first()

        def find(model: Any, name: str) -> int | None:
            return db.execute(
                select(model.id).where(func.lower(model.name) == name.lower())
            ).scalar_one_or_none()

        cats = {}
        for g in dict.fromkeys(x["group"] for x in items):
            cats[g] = (
                find(Category, g) or categories.create_category(db, CategoryCreate(name=g))[0].id
            )
        sups: dict[str, int] = {}
        for s in sorted({x["supplier"] for x in items if x["supplier"]}):
            sid = find(Supplier, s)
            if sid is None:
                # No GST/address known: saved incomplete, flagged "Needs details".
                sup = Supplier(
                    name=s, notes="Added by the Tally stock import; complete GST and address."
                )
                db.add(sup)
                db.commit()
                sid = sup.id
            sups[s] = sid
        added = skipped = 0
        for x in items:
            if (
                find(Product, x["name"]) is not None
                or db.execute(select(Product.id).where(Product.sku == x["sku"])).first()
            ):
                skipped += 1
                continue
            products.create_product(
                db,
                ProductCreate(
                    sku=x["sku"],
                    name=x["name"],
                    description=f"{x['subgroup']} (Tally: {x['group']})"
                    if x["subgroup"]
                    else f"Tally: {x['group']}",
                    supplier_id=sups.get(x["supplier"]),
                    category_id=cats[x["group"]],
                    purchase_cost=round(x["rate"] * 100),
                    sell_price=0,
                    gst_rate_bp=1800,
                    opening_quantity=x["qty"],
                ),
                actor_id=actor,
            )
            added += 1
        print(f"Added {added} products, skipped {skipped} already there.")
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--preview", metavar="OUT.xlsx")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    items = plan(a.file)
    by_group: dict[str, int] = {}
    for x in items:
        by_group[x["group"]] = by_group.get(x["group"], 0) + 1
    print(
        f"{len(items)} items, {sum(x['qty'] for x in items)} units, "
        f"Rs. {sum(x['value'] for x in items):,.2f}; by group {by_group}"
    )
    print(
        "with supplier:",
        sum(1 for x in items if x["supplier"]),
        "blank:",
        sum(1 for x in items if not x["supplier"]),
    )
    if a.preview:
        preview(items, a.preview)
        print("preview written to", a.preview)
    if a.apply:
        apply(items)


if __name__ == "__main__":
    main()
