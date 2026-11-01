# API contract

The agreement between backend and frontend. Anything built in parallel must
match this exactly; if something here is wrong, change this file first and say
so, rather than diverging quietly.

All paths are prefixed `/api`. JSON only. Auth is a session cookie.

> The frontend's `src/api/types.ts` mirrors this file **by hand**. Generating
> it from the OpenAPI schema was the intent, but `openapi-typescript` requires
> TypeScript 5 and this project is on 6, so the generator was removed rather
> than left in the tree pretending to be wired up. Until it can be replaced,
> this document and that file must be changed together.

## Conventions

**Money** is an integer of paise, named `*_paise` in JSON where ambiguous.
Never a float, never formatted server-side.
**GST** is basis points: `1800` means 18%.
**Timestamps** are ISO-8601 UTC with `Z`. The browser renders IST.
**Optional text** is `""`, never `null`. Optional *relations* are `null`.

### Pagination

Every list endpoint takes `?page=` (1-based, default 1) and `?page_size=`
(default 25, max 200) and returns:

```jsonc
{ "items": [...], "total": 137, "page": 1, "page_size": 25, "pages": 6 }
```

### Errors

Never a bare string, never a traceback.

```jsonc
{ "error": { "code": "insufficient_stock", "message": "Only 3 in stock; cannot remove 5.", "details": { "in_stock": 3, "requested": 5 } } }
```

Codes in use: `not_found` (404), `conflict` (409), `insufficient_stock` (409),
`insufficient_reservation` (409), `validation_error` (422),
`invalid_credentials` (401), `not_authenticated` (401), `forbidden` (403),
`rate_limited` (429), `internal_error` (500).

For `validation_error` the per-field detail sits under `details.fields` as
`[{field, message}]`, and the top-level `message` repeats the first of them so
a caller that shows only `message` still says something useful.

## Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/login` | `{email, password}` | `{user: User}` + sets `session` cookie |
| POST | `/auth/logout` | — | `204` |
| GET | `/auth/me` | — | `User`, or `401` |
| POST | `/auth/change-password` | `{current_password, new_password}` | `204` |

```jsonc
// User
{ "id": 1, "email": "admin@excelengineers.in", "full_name": "Admin", "role": "admin" }
```

Cookie: `HttpOnly; SameSite=Lax; Path=/`, `Secure` in production. 8 hours.
`change-password` requires the current password and rotates the session.

## Settings

Singleton, no id in the path.

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/settings` | — | `Settings` |
| PATCH | `/settings` | any subset of the writable fields | `Settings` |

```jsonc
{ "company_name": "Excel Engineers", "low_stock_threshold": 5, "default_gst_rate_bp": 1800 }
```

Theme is **not** here: it is per-viewer, stored in `localStorage["ee-theme"]`.

## Suppliers

| Method | Path | Notes |
|---|---|---|
| GET | `/suppliers` | `?q=&is_active=&page=&page_size=&sort=name\|-name\|-created_at` |
| GET | `/suppliers/options` | Unpaginated `[{id, name}]`, active only. For dropdowns — must not depend on page size. |
| POST | `/suppliers` | `201` |
| GET | `/suppliers/{id}` | includes `product_count` |
| PATCH | `/suppliers/{id}` | all fields optional |
| DELETE | `/suppliers/{id}` | soft delete (`is_active=false`); `409` if products reference it |

```jsonc
// Supplier
{ "id": 3, "name": "KSB Pumps Ltd", "contact_person": "", "phone": "", "email": "",
  "gstin": "", "address_line1": "", "address_line2": "", "city": "", "state": "",
  "pincode": "", "notes": "", "is_active": true, "product_count": 12 }
```

## Categories

`GET /categories` (unpaginated — the list is small), `POST`, `PATCH /{id}`,
`DELETE /{id}` (products fall back to `category: null`).
`{ "id": 1, "name": "Centrifugal Pumps", "product_count": 8 }`

## Products

| Method | Path | Notes |
|---|---|---|
| GET | `/products` | `?q=&supplier_id=&category_id=&is_active=&has_supplier=&page=&page_size=&sort=` |
| POST | `/products` | creates product + inventory row + opening `receive` movement, one transaction |
| GET | `/products/{id}` | |
| PATCH | `/products/{id}` | **never** changes stock |
| DELETE | `/products/{id}` | soft delete |
| GET | `/products/{id}/movements` | paginated, newest first |

`q` searches sku, name and model_number. `has_supplier=false` finds untagged
products — the filter that matters after an import.

```jsonc
// Product
{ "id": 12, "sku": "KSB-ETA-65-200", "name": "KSB Etanorm 65-200",
  "model_number": "65-200", "description": "", "unit": "piece", "hsn_code": "84137010",
  "purchase_cost": 4250000, "sell_price": 5100000, "gst_rate_bp": 1800,
  "is_active": true,
  "supplier": { "id": 3, "name": "KSB Pumps Ltd" },   // or null
  "category": { "id": 1, "name": "Centrifugal Pumps" }, // or null
  "inventory": { "quantity_on_hand": 12, "quantity_reserved": 3, "quantity_available": 9 } }
```

`POST` body adds `opening_quantity` (default 0). `quantity_available` always
comes from the server — the client must never subtract.

## Inventory

| Method | Path | Notes |
|---|---|---|
| GET | `/inventory` | `?q=&supplier_id=&category_id=&stock_status=all\|low\|out\|ok&has_supplier=&page=&page_size=&sort=available\|-available\|name\|-name` |
| GET | `/inventory/summary` | header cards |
| POST | `/inventory/{product_id}/adjust` | `{delta: int, note: str}` → `InventoryRow` |
| PATCH | `/inventory/{product_id}/supplier` | `{supplier_id: int\|null}` → refreshed `InventoryRow` |
| GET | `/inventory/{product_id}/movements` | paginated, newest first |

```jsonc
// InventoryRow
{ "product_id": 12, "sku": "KSB-ETA-65-200", "name": "KSB Etanorm 65-200",
  "model_number": "65-200", "unit": "piece",
  "supplier": { "id": 3, "name": "KSB Pumps Ltd" },   // or null
  "category": { "id": 1, "name": "Centrifugal Pumps" }, // or null
  "quantity_on_hand": 12, "quantity_reserved": 3, "quantity_available": 9,
  "is_low_stock": false, "is_out_of_stock": false }

// Summary
{ "total_products": 340, "low_stock_count": 12, "out_of_stock_count": 3,
  "missing_supplier_count": 27, "total_stock_value_paise": 84250000 }

// Movement
{ "id": 991, "movement_type": "adjust", "on_hand_delta": -2, "reserved_delta": 0,
  "quantity_on_hand_after": 10, "quantity_reserved_after": 3,
  "reference_type": "manual", "reference_id": null, "note": "damaged in transit",
  "created_by": { "id": 1, "full_name": "Admin" },  // or null
  "created_at": "2026-08-30T09:15:00Z" }
```

`is_low_stock` / `is_out_of_stock` are computed **server-side** against the
settings threshold. The client maps them to a colour and never learns the rule.

`movement_type` is one of `adjust | receive | reserve | release | deliver |
import`. `reference_type` is one of `manual | import | order | purchase_order |
challan`. Both mirror `app/constants.py`; there is no `issue`.

## Request bodies

Reads nest related records as `{id, name}`; **writes send bare ids**. Spelling
this out because it is the one asymmetry that is easy to get wrong from the
read shapes alone.

```jsonc
// POST /products
{ "sku": "KSB-ETA-65-200", "name": "KSB Etanorm 65-200", "model_number": "65-200",
  "description": "", "unit": "piece", "hsn_code": "84137010",
  "purchase_cost": 4250000, "sell_price": 5100000, "gst_rate_bp": 1800,
  "supplier_id": 3, "category_id": 1,     // either may be null
  "opening_quantity": 0 }                 // optional, creates a `receive` movement

// PATCH /products/{id} — any subset of the above EXCEPT opening_quantity.
// Stock is never changed through this endpoint.

// POST /suppliers, PATCH /suppliers/{id}
// The Supplier read shape minus `id` and `product_count`. PATCH: any subset.

// POST /categories, PATCH /categories/{id}
{ "name": "Centrifugal Pumps" }

// POST /inventory/{product_id}/adjust
{ "delta": -2, "note": "damaged in transit" }   // delta is signed and non-zero

// PATCH /inventory/{product_id}/supplier
{ "supplier_id": 3 }                            // null clears it
```

## Imports

| Method | Path | Notes |
|---|---|---|
| POST | `/imports/products` | multipart `file` → `202 {id, status}` |
| GET | `/imports/{id}` | poll target |
| GET | `/imports` | paginated history |
| GET | `/imports/template.xlsx` | download |

```jsonc
// ImportJob
{ "id": "0f4c…", "status": "running", "filename": "stock.xlsx",
  "total_rows": 1340, "processed_rows": 600,
  "created_count": 210, "updated_count": 380, "skipped_count": 4, "error_count": 6,
  "errors": [ { "row": 88, "column": "quantity", "message": "not a number", "value": "n/a" } ],
  "column_mapping": { "sku": 0, "name": 1 }, "unmapped_headers": ["Godown"],
  "header_row_index": 3, "message": "",
  "created_at": "…", "started_at": "…", "finished_at": null }
```

`status` is `pending | running | completed | failed`. Poll until terminal.
`total_rows` is 0 until header detection finishes — the bar is indeterminate
until then. `errors` is capped at 200 entries; `error_count` is the true total.

## Customers

Slice 2 lives in its own file: **`contract-customers.md`**. It adds Customers,
`GET /products/lookup` and the settings letterhead block, and it inherits
every convention above.

## Health

`GET /health` → `{ "status": "ok", "db": "ok", "version": "0.1.0" }`
