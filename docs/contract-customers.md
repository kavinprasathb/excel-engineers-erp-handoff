# API contract — Customers (slice 2)

Read `api-contract.md` first: its conventions (paise, `""` vs `null`, the
pagination envelope, the error envelope) apply here unchanged.

Anything built against this must match it exactly. If something here is
wrong, change this file first and say so, rather than diverging quietly.

> The first Quotations build was withdrawn wholesale on 2026-09-18 ahead of a
> redesign. Customers, `GET /products/lookup` and the settings letterhead were
> built alongside it and stay, because whatever replaces it needs all three.

## Customers

Deliberately the same shape as Suppliers — same fields, same verbs, same
sorts — because they are the same kind of record pointed the other way.

| Method | Path | Notes |
|---|---|---|
| GET | `/customers` | `?q=&is_active=&page=&page_size=&sort=name\|-name\|created_at\|-created_at` |
| GET | `/customers/options` | Unpaginated `[{id, name}]`, active only |
| POST | `/customers` | `201` |
| GET | `/customers/{id}` | |
| PATCH | `/customers/{id}` | all fields optional |
| DELETE | `/customers/{id}` | soft delete. Nothing references customers yet, so nothing refuses it; the first module that does (orders) adds the `409` |

`q` searches name and billing city. Name is case-insensitively unique.

```jsonc
// Customer
{ "id": 7, "name": "Chemplast Sanmar Limited", "contact_person": "Mr. B. Prathap",
  "designation": "Purchase", "phone": "", "email": "", "gstin": "",
  "billing_address_line1": "Chloro Chemical Division", "billing_address_line2": "",
  "billing_city": "Mettur Dam", "billing_state": "Tamil Nadu", "billing_pincode": "636403",
  "shipping_address_line1": "", "shipping_address_line2": "",
  "shipping_city": "", "shipping_state": "", "shipping_pincode": "",
  "notes": "", "is_active": true }
```

Blank shipping fields mean "same as billing". Nothing copies one into the
other — not the API, not the PDF, not the form.

```jsonc
// POST /customers — the read shape minus `id`.
// PATCH /customers/{id} — any subset of that.
```

## Product lookup

| Method | Path | Notes |
|---|---|---|
| GET | `/products/lookup` | `?q=&limit=` (default 20, max 50). Active products only |

Declared **before** `/products/{id}` in the router, for the same reason
`/suppliers/options` is.

```jsonc
// ProductLookup — everything the line builder needs, nothing it doesn't
{ "id": 12, "sku": "KSB-ETA-65-200", "name": "KSB Etanorm 65-200",
  "model_number": "65-200", "unit": "piece", "hsn_code": "84137010",
  "sell_price": 5100000, "quantity_available": 9 }
```

`sell_price` is the list price. `purchase_cost` is never sent on this path —
what we paid must not reach a customer-facing screen.

## Settings — additions

`GET`/`PATCH /settings` gain the letterhead. Every field is writable.

```jsonc
{ "company_name": "Excel Engineers", "low_stock_threshold": 5, "default_gst_rate_bp": 1800,
  "company_address_line1": "G2, VKP Residency, 146, Dhayanandhar Street",
  "company_address_line2": "New Fairlands",
  "company_city": "Salem", "company_state": "Tamil Nadu", "company_pincode": "636016",
  "company_gstin": "33AAIFE2328P1Z9",
  "company_phone": "0427 244 0808", "company_mobile": "94449 15716",
  "company_email": "excelengrs@gmail.com",
  "signatory_name": "M. Rajamuthaiyah", "signatory_designation": "" }
```

The letterhead lives here rather than in any document template because the
company's 2020 offers prove it changes, and changing it should be an admin
editing Settings, not a developer editing code and redeploying.
