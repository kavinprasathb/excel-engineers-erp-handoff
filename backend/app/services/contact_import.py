"""Reading customers and suppliers out of someone else's Excel sheet or PDF.

Preview only: nothing here writes to the database. The operator reviews and
edits the proposed records in the browser, and the commit endpoint saves what
they kept. Header-row detection follows the products importer (score each of
the first rows, take the best) and the workbook goes through the same
zip-bomb guard (`importer.runner.read_rows`).

The PDF side is heuristics over extracted text: regexes for emails, Indian
phone numbers, GSTINs and pincodes, plus "Label: value" lines. It will not be
perfect, which is exactly why there is a review step.
"""

import difflib
import io
import re
from typing import Any, Final, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..errors import ValidationFailed
from ..models import Customer, Supplier
from ..schemas.contacts import PHONE_RE
from .importer.headers import normalise
from .importer.runner import ImportAborted, read_rows

Kind = Literal["customer", "supplier"]

MAX_RECORDS: Final = 2_000
MAX_HEADER_SCAN_ROWS: Final = 25

FIELDS: Final[dict[str, set[str]]] = {
    "name": {
        "name",
        "company",
        "company name",
        "customer",
        "customer name",
        "supplier",
        "supplier name",
        "vendor",
        "vendor name",
        "party",
        "party name",
        "firm",
        "firm name",
        "organisation",
        "organization",
    },
    "contact_person": {"contact person", "contact name", "contact", "person", "kind attn", "attn"},
    "designation": {"designation", "title", "position", "role"},
    "emails": {"email", "emails", "e mail", "email id", "email address", "mail", "mail id"},
    "phones": {
        "phone",
        "phones",
        "phone no",
        "phone number",
        "mobile",
        "mobile no",
        "mobile number",
        "contact no",
        "contact number",
        "tel",
        "telephone",
        "cell",
        "whatsapp",
    },
    "gstin": {"gstin", "gst no", "gst number", "gst", "gstin no", "gst in"},
    "address_line1": {"address", "address line 1", "address 1", "address1", "street"},
    "address_line2": {"address line 2", "address 2", "address2", "area", "locality"},
    "city": {"city", "town", "district"},
    "state": {"state"},
    "pincode": {"pincode", "pin", "pin code", "postal code", "zip", "zip code"},
    "notes": {"notes", "note", "remarks", "remark", "comments"},
}
_ORDER: Final = tuple(FIELDS)

EMAIL_RE: Final = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
GSTIN_RE: Final = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
PIN_RE: Final = re.compile(r"(?<!\d)\d{3}\s?\d{3}(?!\d)")
PHONE_FIND_RE: Final = re.compile(
    r"(?:\+91[\s\-]?)?(?<!\d)[6-9]\d{4}[\s\-]?\d{5}(?!\d)"  # mobiles
    r"|(?<!\d)0\d{2,4}[\s\-]?\d{6,8}(?!\d)"  # STD landlines
)
SPLIT_RE: Final = re.compile(r"[,;/\n]+")
LABEL_RE: Final = re.compile(r"^\s*([A-Za-z][A-Za-z .()/_\-]{0,30}?)\s*[:\-]\s*(.*)$")


def _match(header: object) -> str | None:
    text = normalise(header)
    if not text:
        return None
    for field in _ORDER:
        if text in FIELDS[field]:
            return field
    for field in _ORDER:
        if difflib.get_close_matches(text, FIELDS[field], n=1, cutoff=0.85):
            return field
    return None


def _map(row: tuple[object, ...]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(row):
        field = _match(cell)
        if field and field not in mapping:
            mapping[field] = index
    return mapping


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _split(value: str) -> list[str]:
    return [part.strip() for part in SPLIT_RE.split(value) if part.strip()]


def _blank() -> dict[str, Any]:
    return {field: [] if field in ("emails", "phones") else "" for field in FIELDS}


def parse_xlsx(data: bytes) -> list[dict[str, Any]]:
    try:
        rows = read_rows(data)
    except ImportAborted as exc:
        raise ValidationFailed(str(exc)) from exc
    best, best_score = None, 0
    for index, row in enumerate(rows[:MAX_HEADER_SCAN_ROWS]):
        score = len(_map(row))
        if score > best_score:
            best, best_score = index, score
    if best is None or best_score < 2 or "name" not in _map(rows[best]):
        raise ValidationFailed(
            "Could not find a header row with a Name column (and at least one other "
            "column such as Email, Phone or GSTIN) in the first sheet."
        )
    mapping = _map(rows[best])
    out: list[dict[str, Any]] = []
    for row in rows[best + 1 :]:
        record = _blank()
        for field, col in mapping.items():
            value = _text(row[col]) if col < len(row) else ""
            if field in ("emails", "phones"):
                record[field] = _split(value)
            else:
                record[field] = value
        if not any(record.values()):
            continue
        out.append(record)
    return out


def _labelled(label: str) -> str | None:
    return _match(label)


def parse_pdf_text(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current = _blank()

    def flush() -> None:
        nonlocal current
        if any(current.values()):
            records.append(current)
        current = _blank()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        field: str | None = None
        value = line
        m = LABEL_RE.match(line)
        if m:
            field = _labelled(m.group(1))
            if field:
                value = m.group(2).strip()
        if field == "name" and current["name"]:
            flush()
        # Pull structured tokens out of the line wherever they appear.
        for email in EMAIL_RE.findall(value):
            current["emails"].append(email)
        rest = EMAIL_RE.sub(" ", value)
        gst = GSTIN_RE.search(rest.upper())
        if gst and not current["gstin"]:
            current["gstin"] = gst.group(0)
        rest = GSTIN_RE.sub(" ", rest)
        for phone in PHONE_FIND_RE.findall(rest):
            current["phones"].append(" ".join(phone.split()))
        rest = PHONE_FIND_RE.sub(" ", rest)
        if field in ("emails", "phones", "gstin"):
            if field == "phones" and not current["phones"] and rest.strip():
                current["phones"].extend(_split(rest))
            continue
        if field == "pincode":
            pin = PIN_RE.search(rest)
            current["pincode"] = pin.group(0).replace(" ", "") if pin else rest.strip()
            continue
        if field:
            if field == "address_line1" and current["address_line1"]:
                field = "address_line2"
            if field in ("address_line1", "address_line2"):
                pin = PIN_RE.search(rest)
                if pin and not current["pincode"]:
                    current["pincode"] = pin.group(0).replace(" ", "")
            current[field] = f"{current[field]}, {value}".strip(", ") if current[field] else value
            continue
        # Unlabelled line: name first, then address.
        leftover = " ".join(rest.replace("|", " ").split()).strip(" ,;:-")
        pin = PIN_RE.search(leftover)
        if pin and not current["pincode"] and current["name"]:
            current["pincode"] = pin.group(0).replace(" ", "")
            leftover = PIN_RE.sub("", leftover).strip(" ,;:-")
        if not leftover or re.fullmatch(r"(?i)(phone|mobile|email|tel|gst\w*)", leftover):
            continue
        if not current["name"]:
            current["name"] = leftover
        elif not current["address_line1"]:
            current["address_line1"] = leftover
        elif not current["address_line2"]:
            current["address_line2"] = leftover
        else:
            current["address_line2"] = f"{current['address_line2']}, {leftover}"
    flush()
    return records


def parse_pdf(data: bytes) -> list[dict[str, Any]]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise ValidationFailed("That file could not be read as a PDF.") from exc
    if not text.strip():
        raise ValidationFailed(
            "No text could be read from that PDF. Scanned images are not supported."
        )
    return parse_pdf_text(text)


def _to_payload(record: dict[str, Any], kind: Kind) -> dict[str, Any]:
    def cap(value: str, n: int) -> str:
        return value[:n]

    emails = list(dict.fromkeys(e.strip() for e in record["emails"] if e.strip()))
    phones = list(dict.fromkeys(" ".join(p.split()) for p in record["phones"] if p.strip()))
    base: dict[str, Any] = {
        "name": cap(record["name"], 200),
        "contact_person": cap(record["contact_person"], 150),
        "emails": emails[:10],
        "phones": phones[:10],
        "gstin": cap(record["gstin"].upper().replace(" ", ""), 20),
        "notes": record["notes"],
        "is_active": True,
    }
    if kind == "customer":
        base.update(
            designation=cap(record["designation"], 100),
            billing_address_line1=cap(record["address_line1"], 255),
            billing_address_line2=cap(record["address_line2"], 255),
            billing_city=cap(record["city"], 100),
            billing_state=cap(record["state"], 100),
            billing_pincode=cap(record["pincode"].replace(" ", ""), 10),
        )
    else:
        base.update(
            address_line1=cap(record["address_line1"], 255),
            address_line2=cap(record["address_line2"], 255),
            city=cap(record["city"], 100),
            state=cap(record["state"], 100),
            pincode=cap(record["pincode"].replace(" ", ""), 10),
        )
    return base


def _warnings(payload: dict[str, Any], kind: Kind) -> list[str]:
    warnings: list[str] = []
    if not payload["name"]:
        warnings.append("No name found.")
    for email in payload["emails"]:
        if not EMAIL_RE.fullmatch(email):
            warnings.append(f"'{email}' does not look like an email address.")
    for phone in payload["phones"]:
        if not PHONE_RE.match(phone):
            warnings.append(f"'{phone}' does not look like a phone number.")
    if payload["gstin"] and not GSTIN_RE.fullmatch(payload["gstin"]):
        warnings.append(f"GSTIN '{payload['gstin']}' does not look valid.")
    pin = payload["billing_pincode" if kind == "customer" else "pincode"]
    if pin and not re.fullmatch(r"\d{6}", pin):
        warnings.append(f"Pincode '{pin}' is not 6 digits.")
    return warnings


def preview(db: Session, *, kind: Kind, filename: str, data: bytes) -> dict[str, Any]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix in ("xlsx", "xlsm"):
        raw = parse_xlsx(data)
    elif suffix == "pdf":
        raw = parse_pdf(data)
    else:
        raise ValidationFailed("Only Excel (.xlsx) or PDF files can be imported.")

    truncated = len(raw) > MAX_RECORDS
    raw = raw[:MAX_RECORDS]
    payloads = [_to_payload(r, kind) for r in raw]

    model: Any = Customer if kind == "customer" else Supplier
    names = {p["name"].strip().lower() for p in payloads if p["name"].strip()}
    gstins = {p["gstin"] for p in payloads if p["gstin"]}
    by_name: dict[str, tuple[int, str]] = {}
    by_gstin: dict[str, tuple[int, str]] = {}
    if names:
        for row in db.execute(
            select(model.id, model.name).where(func.lower(model.name).in_(names))
        ):
            by_name[row[1].lower()] = (row[0], row[1])
    if gstins:
        for row in db.execute(
            select(model.id, model.name, model.gstin).where(model.gstin.in_(gstins))
        ):
            by_gstin[row[2]] = (row[0], row[1])

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in payloads:
        warnings = _warnings(payload, kind)
        key = payload["name"].strip().lower()
        hit = by_gstin.get(payload["gstin"]) if payload["gstin"] else None
        hit = hit or by_name.get(key)
        if hit:
            warnings.append(f"Possible duplicate of existing {kind} '{hit[1]}'.")
        if key and key in seen:
            warnings.append("The same name appears earlier in this file.")
        seen.add(key)
        records.append(
            {
                "data": payload,
                "warnings": warnings,
                "duplicate_of": {"id": hit[0], "name": hit[1]} if hit else None,
            }
        )
    return {"records": records, "truncated": truncated}


def commit(db: Session, *, kind: Kind, bodies: list[Any]) -> int:
    """Create every record in one transaction: all of them, or none."""
    model: Any = Customer if kind == "customer" else Supplier
    names = [b.name.strip() for b in bodies]
    seen: dict[str, int] = {}
    for index, name in enumerate(names):
        key = name.lower()
        if key in seen:
            raise ValidationFailed(
                f"Rows {seen[key] + 1} and {index + 1} have the same name '{name}'.",
                row=index,
            )
        seen[key] = index
    if seen:
        existing = (
            db.execute(select(model.name).where(func.lower(model.name).in_(list(seen))))
            .scalars()
            .all()
        )
        if existing:
            first = existing[0]
            raise ValidationFailed(
                f"A {kind} named '{first}' already exists (row {seen[first.lower()] + 1}).",
                row=seen[first.lower()],
                existing=list(existing),
            )
    for body, name in zip(bodies, names, strict=True):
        db.add(model(**{**body.model_dump(), "name": name}))
    db.commit()
    return len(bodies)
