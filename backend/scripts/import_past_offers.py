"""Items from the past offer letters, for description suggestions while quoting.

Run from the backend folder:

    uv run python -m scripts.import_past_offers \
        "D:/Excel Engg/3. Executed" "D:/Excel Engg/1.Live Offer" --preview out.xlsx
    uv run python -m scripts.import_past_offers \
        "D:/Excel Engg/3. Executed" "D:/Excel Engg/1.Live Offer" --apply

What is read from each Word offer (files whose header carries an ESQ...
number; drafts "~$..." are skipped):

* the header: customer (line 1, "M/s." removed), offer number, date;
* HSN: the "HSN code 84139120" in the terms, for every item of the offer;
* spares tables: every row with a description and a rate, with its part
  no, MOC, unit and quantity where the table has those columns, and the
  "Model: ..." heading above the table as the item's details;
* pump letters (price written in text): each "Pump Model : X" with the
  "Rs. 3,12,500/- Each Set" that follows it, and the scope line as details.

The customer is the one the app already has for that offer folder (the list
in import_offer_customers), else the name in the header. Revisions of one
offer repeat its items: an item (description, rate, customer) is kept once,
from the newest letter. --apply replaces the whole table, so it is safe to
rerun; nothing else in the database is touched.
"""

import argparse
import glob
import os
import re
import zipfile
from datetime import date
from typing import Any

from openpyxl import Workbook  # type: ignore[import-untyped]
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.models import Customer, PastOfferItem
from scripts.import_offer_customers import C as KNOWN_CUSTOMERS

OFFER_NO = re.compile(
    r"(ESQ[A-Z]*)\s*-?\s*(\d{2})\s*-?\s*(\d{1,4})\s*(R\s*\d+|[A-Z](?![a-z]))?", re.I
)
DATE = re.compile(r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})")
# The letters are typed in Word, so dashes are often en dashes (U+2013).
HSN = re.compile(r"HSN\s*(?:code)?\s*[:\-\u2013]?\s*(\d{4,8})", re.I)
MONEY = re.compile(r"(\d[\d,]*(?:\.\d{1,2})?)")
PRICE_IN_TEXT = re.compile(r"Rs\.?\s*([\d,]+(?:\.\d{1,2})?)\s*/?-?", re.I)


def _plain(xml: str) -> str:
    t = re.sub(r"</w:p>", "\n", xml)
    t = re.sub(r"<w:br/>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')


def _cells(table_xml: str) -> list[list[str]]:
    rows = []
    for tr in re.findall(r"<w:tr[ >].*?</w:tr>", table_xml, re.S):
        rows.append(
            [
                "\n".join(" ".join(x.split()) for x in _plain(tc).split("\n") if x.strip())
                for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)
            ]
        )
    return rows


def _rupees(text: str) -> int | None:
    m = MONEY.search(text.replace(" ", ""))
    if not m:
        return None
    try:
        v = round(float(m.group(1).replace(",", "")) * 100)
    except ValueError:
        return None
    return v if v > 0 else None


def _date(text: str) -> date | None:
    m = DATE.search(text)
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    y = y + 2000 if y < 100 else y
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _role(cell: str) -> str:
    c = cell.lower()
    if re.search(r"part\s*n", c):
        return "part"
    if re.search(r"\bmoc\b|material", c):
        return "moc"
    if re.search(r"desc|particular|item|parts|scope", c) and not re.search(r"item\s*no", c):
        return "desc"
    if re.search(r"\bqty|quantity", c):
        return "qty"
    if re.search(r"^unit$|uom", c):
        return "unit"
    if re.search(r"total|amount", c):
        return "total"
    if re.search(r"rate|price", c):
        return "rate"
    return ""


def read_offer(path: str) -> dict[str, Any] | None:
    try:
        xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf8", "ignore")
    except (zipfile.BadZipFile, KeyError):
        return None
    text = _plain(xml)
    lines = [" ".join(s.split()) for s in text.split("\n") if s.strip()]
    head = " ".join(lines[:6])
    num = OFFER_NO.search(head)
    if not num:
        return None
    first = OFFER_NO.split(lines[0])[0] if OFFER_NO.search(lines[0]) else lines[0]
    customer = re.sub(r"(?i)^\s*m\s*/\s*s\.?\s*", "", first).strip(" ,.")
    hsn = HSN.search(text)
    offer: dict[str, Any] = {
        "offer_no": f"{num.group(1).upper()}-{num.group(2)}-{num.group(3)}"
        f"{(num.group(4) or '').replace(' ', '').upper()}",
        "date": _date(" ".join(lines[1:4])),
        "customer": customer[:200],
        "hsn": hsn.group(1) if hsn else "",
        "items": [],
    }
    offer["folder"] = os.path.basename(os.path.dirname(path))[:6]

    # Spares tables: a header row naming a description and a price column.
    body = re.split(r"(<w:tbl>.*?</w:tbl>)", xml, flags=re.S)
    heading = ""
    for part in body:
        if not part.startswith("<w:tbl>"):
            before = [" ".join(s.split()) for s in _plain(part).split("\n") if s.strip()]
            for b in before[-3:]:
                if len(b) <= 120 and re.search(
                    r"(?i)^(pump\s*)?model\s*[:\-]|pump\s*set\s*$|pumpset\s*$", b
                ):
                    heading = b[:300]
            continue
        rows = _cells(part)
        hdr = next(
            (
                i
                for i, r in enumerate(rows)
                if {"desc"} <= {_role(c) for c in r} and {"rate", "total"} & {_role(c) for c in r}
            ),
            None,
        )
        if hdr is None:
            continue
        roles = [_role(c) for c in rows[hdr]]
        if "rate" not in roles and "total" in roles:
            roles[roles.index("total")] = "rate"  # a single price column
        for r in rows[hdr + 1 :]:
            cells = dict(zip(roles, r, strict=False))
            desc = (cells.get("desc") or "").strip()
            rate = _rupees(cells.get("rate", ""))
            if not desc or not rate or re.match(r"(?i)^(total|grand total|sub\s*total)", desc):
                continue
            first_line, _, rest = desc.partition("\n")
            qty_text = cells.get("qty", "")
            qty = int(m.group(0)) if (m := re.search(r"\d+", qty_text)) else 1
            unit = (cells.get("unit") or re.sub(r"[\d\s]+", " ", qty_text)).strip()[:30]
            offer["items"].append(
                {
                    "description": first_line[:2000],
                    "details": "\n".join(x for x in (heading, rest.strip()) if x)[:2000],
                    "part_no": (cells.get("part") or "")[:60],
                    "moc": (cells.get("moc") or "")[:60],
                    "unit": unit,
                    "quantity": max(qty, 1),
                    "rate": rate,
                }
            )

    # Pump letters: the price is written in the text after each pump model.
    if not offer["items"]:
        model = ""
        for i, ln in enumerate(lines):
            m = re.match(r"(?i)pump\s*model\s*[:\-]?\s*(.+)", ln)
            if m:
                model = m.group(1).strip()
                continue
            price = PRICE_IN_TEXT.search(ln)
            if price and model and re.search(r"(?i)each|set|per|/-", ln):
                rate = _rupees(price.group(1))
                if not rate:
                    continue
                scope = re.sub(r"(?i)\s*[-\u2013]?\s*Rs\.?.*$", "", ln).strip(" -\u2013,")
                if (
                    i
                    and re.search(r"(?i)^supply", lines[i - 1])
                    and not re.search(r"(?i)^supply", scope)
                ):
                    scope = f"{lines[i - 1]} {scope}"
                offer["items"].append(
                    {
                        "description": model[:2000],
                        "details": scope[:2000],
                        "part_no": "",
                        "moc": "",
                        "unit": "Set" if re.search(r"(?i)set", ln) else "No",
                        "quantity": 1,
                        "rate": rate,
                    }
                )
    return offer


def collect(roots: list[str]) -> list[dict[str, Any]]:
    by_folder = {p: c["name"] for c in KNOWN_CUSTOMERS for p in c["src"] + c.get("pdf_also", [])}
    offers = []
    for root in roots:
        files = glob.glob(os.path.join(root, "*", "*.docx")) + glob.glob(
            os.path.join(root, "*.docx")
        )
        for f in sorted(files):
            if os.path.basename(f).startswith("~$"):
                continue
            o = read_offer(f)
            if o and o["items"]:
                o["source"] = os.path.relpath(f, os.path.dirname(root))[:300]
                o["customer"] = by_folder.get(o["folder"], o["customer"])
                offers.append(o)
    # Newest letter first, so a repeated item keeps its latest rate and date.
    offers.sort(key=lambda o: o["date"] or date.min, reverse=True)
    seen: set[tuple[str, int, str]] = set()
    items = []
    for o in offers:
        for it in o["items"]:
            key = (" ".join(it["description"].lower().split()), it["rate"], o["customer"].lower())
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {**it, **{k: o[k] for k in ("offer_no", "date", "customer", "hsn", "source")}}
            )
    return items


def preview(items: list[dict[str, Any]], out: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Past offer items"
    ws.append(
        [
            "Date",
            "Offer",
            "Customer",
            "Description",
            "Details",
            "Part No",
            "MOC",
            "Qty",
            "Unit",
            "Rate (Rs.)",
            "HSN",
            "File",
        ]
    )
    for it in items:
        ws.append(
            [
                it["date"],
                it["offer_no"],
                it["customer"],
                it["description"],
                it["details"],
                it["part_no"],
                it["moc"],
                it["quantity"],
                it["unit"],
                it["rate"] / 100,
                it["hsn"],
                it["source"],
            ]
        )
    wb.save(out)


def apply(items: list[dict[str, Any]]) -> None:
    db = SessionLocal()
    try:
        ids = {n.lower(): i for i, n in db.execute(select(Customer.id, Customer.name)).all()}
        db.execute(delete(PastOfferItem))
        for it in items:
            db.add(
                PastOfferItem(
                    description=it["description"],
                    details=it["details"],
                    part_no=it["part_no"],
                    moc=it["moc"],
                    unit=it["unit"],
                    quantity=it["quantity"],
                    rate_paise=it["rate"],
                    hsn_code=it["hsn"],
                    offer_no=it["offer_no"],
                    offer_date=it["date"],
                    customer_name=it["customer"],
                    customer_id=ids.get(it["customer"].lower()),
                    source=it["source"],
                )
            )
        db.commit()
        n = db.execute(select(func.count()).select_from(PastOfferItem)).scalar_one()
        linked = db.execute(
            select(func.count())
            .select_from(PastOfferItem)
            .where(PastOfferItem.customer_id.is_not(None))
        ).scalar_one()
        print(f"Loaded {n} past offer items; {linked} linked to a customer in the app.")
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--preview", metavar="OUT.xlsx")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    items = collect(a.folders)
    offers = {it["offer_no"] for it in items}
    print(
        f"{len(items)} items from {len(offers)} offers; "
        f"{sum(1 for it in items if it['hsn'])} with HSN, "
        f"{sum(1 for it in items if it['date'])} dated"
    )
    if a.preview:
        preview(items, a.preview)
        print("preview written to", a.preview)
    if a.apply:
        apply(items)


if __name__ == "__main__":
    main()
