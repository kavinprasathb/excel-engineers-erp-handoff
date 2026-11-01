# Quotations — design (2026-09-19)

Rebuild of the quotation module against the client's real letter format
(`ESQSP 26-70`, Salem Steel Plant, 20.04.2026). Approved by Kavin in chat.

## Decisions
- Output is a **PDF rendered by the app** (ReportLab), not a filled Word/Excel file.
- Line items are **either** a product picked from the catalogue **or** free text. Every
  field on a line is editable, including the rate on a product line. **No price floor.**
- Numbering matches current practice: three types with their own prefix and sequence —
  `ESQP` (pumps), `ESQV` (valves), `ESQSP` (spares). Format `<PREFIX>-<YY>-<seq>` with
  `R<n>` appended for revisions ≥ 1. Sequence restarts each year. One function; change later.
- Unlimited revisions. Revising a quote locks the old one as `superseded` and opens
  `R(n+1)` for editing. Only the latest revision can change status.
- Statuses: `pending` → `accepted` | `declined`; plus `superseded` for old revisions.
  Accepting is only a flag for now; Orders will hook in later.
- Terms: per-type defaults live in Settings (ordered label + text). A new quote copies
  them all; each line carries a checkbox (`included`, default on) and editable text.
- Header free text: `subject` and `reference` only.

## Data
- `quotations`: id, type, year, seq, revision, number (denormalised, e.g. `ESQSP-26-70R1`),
  customer_id FK, quote_date, subject, reference, status, supersedes_id FK self NULL,
  created_by_id, timestamps. Unique `(type, year, seq, revision)`.
- `quotation_lines`: quotation_id FK cascade, position, product_id FK NULL, description,
  quantity int > 0, rate_paise bigint ≥ 0. Value computed on read.
- `quotation_terms`: quotation_id FK cascade, position, label, text, included bool.
- `quotation_counters`: (type, year) PK, last_seq. Row locked `FOR UPDATE` on allocation.
- `app_settings.quotation_terms_defaults` JSONB `{type: [{label, text}]}` seeded from
  the client's letters.

## API (`/api/quotations`)
list (q, type, status, customer_id, page, sort) · create · get · patch (header, lines,
terms replaced wholesale) · `POST /{id}/revise` · `POST /{id}/status` · `GET /{id}/pdf`.
Settings GET/PATCH include `quotation_terms_defaults`.

## PDF
Letterhead: Excel Engineers logo left, KSB logo right, rule. Customer name + billing
address, number and dd.mm.yyyy date on the right. `Dear Sir,` / `Sub.:` / `Ref.:` /
`*****` / intro sentence repeating the subject. Table S.No | Item Description | Qty |
Rate | Value In Rs. in whole rupees, Total row when more than one line. "Commercial
Terms & Conditions:" then included terms as `Label : text`. Two fixed closing
paragraphs, `Regards,`, stamp/signature image, signatory name and mobile from Settings.
Images are static assets in the repo. Verified by screenshot against the original.

## UI
`/quotations` list (status badges, type/status filters, search). `/quotations/new` and
`/quotations/:id` share one editor: customer picker, type, date, subject, reference,
line table (product search or free text, inline qty/rate, value), terms with checkbox +
editable text, actions Save / PDF / Revise / Accept / Decline. Settings gets a
"Quotation terms" card per type.

## Tests
Numbering under concurrent allocation; revision and status rules; PDF endpoint returns
a PDF with the number in it; settings defaults round-trip; frontend list and editor.

## Addendum — Format 2 "Technical offer" (2026-09-19, approved)

Source: `20-085-Chemplast -MCPK 125-80-200 CD4MU pump offer.doc` (Aug 2020).

- `quotations.format` ∈ {1, 2}; chosen on create, fixed once numbered. Everything
  else (numbering, revisions, statuses, terms, decline reason) is shared.
- **Technical details**: `quotation_specs` — ordered `label : value` rows, fully
  dynamic. New format-2 quotes seed from `app_settings.quotation_spec_defaults`
  (Pump Model, Liquid Handled, Capacity (Cub.M/hr), Total Head (Mtrs), Shaft Seal,
  Recommended Motor (kW)); editable in Settings.
- **Scope of supply and price**: `quotation_lines` gains `kind` (product | note) and
  `unit_label` (default "Each"). Product rows print `desc — Rs. 2,16,000/- Each`;
  note rows print as text ("KSB Make", "Fitted with Mechanical Seal (Bare Pump)").
  Notes have quantity 1 and rate 0. No quantity in this format.
- **PDF**: same letterhead/closing as format 1; regular serif body; intro "…Based on
  the data provided by you, we are submitting our offer for {subject}."; letterhead
  footer (address, GSTIN, phone, mobile, email) on every page; multi-page.
