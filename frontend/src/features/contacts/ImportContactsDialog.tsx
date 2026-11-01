import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Modal } from "../../components/ui/Modal";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { errorCardCls } from "../../components/ui/styles";
import { useToast } from "../../components/ui/toast-context";
import { api } from "../../api/client";
import { errorMessage } from "../../lib/errors";
import type { ImportCommitResult, ImportPreview, Ref } from "../../api/types";
import { contactError, splitContacts } from "./contactValues";

export type ImportKind = "customers" | "suppliers";

/** The text columns the preview table edits, per kind. Emails/phones are separate. */
const COLUMNS: Record<ImportKind, { key: string; label: string; width?: string }[]> = {
  customers: [
    { key: "name", label: "Name", width: "min-w-48" },
    { key: "contact_person", label: "Contact person" },
    { key: "designation", label: "Designation" },
    { key: "gstin", label: "GSTIN" },
    { key: "billing_address_line1", label: "Address line 1", width: "min-w-48" },
    { key: "billing_address_line2", label: "Address line 2" },
    { key: "billing_city", label: "City" },
    { key: "billing_state", label: "State" },
    { key: "billing_pincode", label: "Pincode", width: "min-w-24" },
    { key: "notes", label: "Notes" },
  ],
  suppliers: [
    { key: "name", label: "Name", width: "min-w-48" },
    { key: "contact_person", label: "Contact person" },
    { key: "gstin", label: "GSTIN" },
    { key: "address_line1", label: "Address line 1", width: "min-w-48" },
    { key: "address_line2", label: "Address line 2" },
    { key: "city", label: "City" },
    { key: "state", label: "State" },
    { key: "pincode", label: "Pincode", width: "min-w-24" },
    { key: "notes", label: "Notes" },
  ],
};

type RawRecord = Record<string, unknown>;

interface ImportRow {
  key: number;
  fields: Record<string, string>;
  emails: string;
  phones: string;
  warnings: string[];
  duplicate: Ref | null;
}

function toRow(data: RawRecord, warnings: string[], duplicate: Ref | null, key: number): ImportRow {
  const fields: Record<string, string> = {};
  for (const [k, v] of Object.entries(data)) {
    if (typeof v === "string") fields[k] = v;
  }
  const list = (v: unknown) => (Array.isArray(v) ? v.filter((x) => typeof x === "string") : []);
  return {
    key,
    fields,
    emails: list(data.emails).join(", "),
    phones: list(data.phones).join(", "),
    warnings,
    duplicate,
  };
}

function rowProblems(row: ImportRow): string[] {
  const problems: string[] = [];
  if (!(row.fields.name ?? "").trim()) problems.push("Name is required.");
  for (const e of splitContacts(row.emails)) {
    if (contactError("email", e)) problems.push(`'${e}' is not a valid email.`);
  }
  for (const p of splitContacts(row.phones)) {
    if (contactError("phone", p)) problems.push(`'${p}' is not a valid phone number.`);
  }
  if (splitContacts(row.emails).length > 10) problems.push("At most 10 emails.");
  if (splitContacts(row.phones).length > 10) problems.push("At most 10 phone numbers.");
  return problems;
}

function toPayload(row: ImportRow): RawRecord {
  const out: RawRecord = { ...row.fields, is_active: true };
  for (const [k, v] of Object.entries(row.fields)) out[k] = v.trim();
  out.emails = splitContacts(row.emails);
  out.phones = splitContacts(row.phones);
  return out;
}

export function ImportContactsDialog({
  kind,
  open,
  onClose,
}: {
  kind: ImportKind;
  open: boolean;
  onClose: () => void;
}) {
  const toast = useToast();
  const client = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<ImportRow[] | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [dragging, setDragging] = useState(false);
  const noun = kind === "customers" ? "customer" : "supplier";

  const preview = useMutation({
    meta: { silent: true },
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<ImportPreview<RawRecord>>(`/${kind}/import/preview`, form);
    },
    onSuccess: (result) => {
      setRows(result.records.map((r, i) => toRow(r.data, r.warnings, r.duplicate_of, i)));
      setTruncated(result.truncated);
    },
  });

  const commit = useMutation({
    meta: { silent: true },
    mutationFn: (records: RawRecord[]) =>
      api.post<ImportCommitResult>(`/${kind}/import/commit`, { records }),
    onSuccess: (result) => {
      client.invalidateQueries({ queryKey: [kind] });
      toast.success(`${result.created} ${noun}${result.created === 1 ? "" : "s"} imported.`);
      close();
    },
  });

  function close() {
    setRows(null);
    setTruncated(false);
    preview.reset();
    commit.reset();
    onClose();
  }

  function pick(file: File | undefined) {
    if (!file) return;
    commit.reset();
    preview.mutate(file);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    pick(event.dataTransfer.files[0]);
  }

  function edit(key: number, patch: Partial<ImportRow>) {
    setRows((prev) => prev?.map((r) => (r.key === key ? { ...r, ...patch } : r)) ?? null);
  }

  function setField(key: number, field: string, value: string) {
    setRows(
      (prev) =>
        prev?.map((r) => (r.key === key ? { ...r, fields: { ...r.fields, [field]: value } } : r)) ??
        null,
    );
  }

  const invalid = rows?.some((r) => rowProblems(r).length > 0) ?? false;
  const count = rows?.length ?? 0;
  const columns = COLUMNS[kind];

  return (
    <Modal
      open={open}
      onClose={close}
      wide={rows !== null}
      title={`Import ${kind}`}
      description="Excel (.xlsx) or PDF, up to 10 MB. Review and edit before anything is saved."
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          {rows ? (
            <Button
              variant="primary"
              disabled={!count || invalid}
              loading={commit.isPending}
              onClick={() => commit.mutate(rows.map(toPayload))}
            >
              Save {count} record{count === 1 ? "" : "s"}
            </Button>
          ) : null}
        </>
      }
    >
      <div className="space-y-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`rounded-xl border border-dashed p-5 text-center text-[13px] ${
            dragging ? "border-ink bg-hoverfill" : "border-line"
          }`}
        >
          <p className="text-ink-2">Drop a file here, or</p>
          <Button
            size="sm"
            className="mt-2"
            loading={preview.isPending}
            onClick={() => inputRef.current?.click()}
          >
            Choose file
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            aria-label="Import file"
            onChange={(e) => {
              pick(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>

        {preview.error || commit.error ? (
          <div className={errorCardCls} role="alert">
            <p className="text-[13px] font-medium text-red">
              {preview.error ? "Could not read that file" : "Nothing was saved"}
            </p>
            <p className="mt-0.5 text-[13px] text-ink-2">
              {errorMessage(preview.error ?? commit.error)}
            </p>
          </div>
        ) : null}

        {truncated ? (
          <p className="text-[13px] text-amber">Only the first 2,000 records are shown.</p>
        ) : null}

        {rows && !rows.length ? (
          <p className="text-[13px] text-ink-2">No records were found in that file.</p>
        ) : null}

        {rows && rows.length ? (
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-left text-[12px] text-ink-2">
                  <th className="p-2">#</th>
                  {columns.slice(0, 2).map((c) => (
                    <th key={c.key} className="p-2 font-medium">
                      {c.label}
                    </th>
                  ))}
                  <th className="p-2 font-medium">Emails (comma-separated)</th>
                  <th className="p-2 font-medium">Phones (comma-separated)</th>
                  {columns.slice(2).map((c) => (
                    <th key={c.key} className="p-2 font-medium">
                      {c.label}
                    </th>
                  ))}
                  <th className="p-2" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => {
                  const problems = rowProblems(row);
                  const notes = [...problems, ...row.warnings];
                  const cell = (c: { key: string; label: string; width?: string }) => (
                    <td key={c.key} className={`p-1.5 align-top ${c.width ?? "min-w-36"}`}>
                      <Input
                        aria-label={`Row ${index + 1} ${c.label}`}
                        value={row.fields[c.key] ?? ""}
                        invalid={c.key === "name" && !(row.fields.name ?? "").trim()}
                        onChange={(e) => setField(row.key, c.key, e.target.value)}
                      />
                    </td>
                  );
                  return (
                    <tr key={row.key} className="border-t border-line">
                      <td className="p-2 align-top text-ink-2">
                        {index + 1}
                        {notes.length ? (
                          <span
                            className={`ml-1 ${problems.length ? "text-red" : "text-amber"}`}
                            title={notes.join("\n")}
                            aria-label={notes.join(" ")}
                          >
                            ⚠
                          </span>
                        ) : null}
                      </td>
                      {columns.slice(0, 2).map(cell)}
                      <td className="min-w-56 p-1.5 align-top">
                        <Input
                          aria-label={`Row ${index + 1} Emails`}
                          value={row.emails}
                          invalid={splitContacts(row.emails).some((e) => contactError("email", e))}
                          onChange={(e) => edit(row.key, { emails: e.target.value })}
                        />
                      </td>
                      <td className="min-w-48 p-1.5 align-top">
                        <Input
                          aria-label={`Row ${index + 1} Phones`}
                          value={row.phones}
                          invalid={splitContacts(row.phones).some((p) => contactError("phone", p))}
                          onChange={(e) => edit(row.key, { phones: e.target.value })}
                        />
                      </td>
                      {columns.slice(2).map(cell)}
                      <td className="p-1.5 align-top">
                        <button
                          type="button"
                          aria-label={`Remove row ${index + 1}`}
                          title="Remove row"
                          onClick={() =>
                            setRows((prev) => prev?.filter((r) => r.key !== row.key) ?? null)
                          }
                          className="grid h-9 w-9 place-items-center rounded-lg text-[18px] text-ink-2 hover:bg-hoverfill hover:text-ink"
                        >
                          ×
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}

        {rows?.some((r) => r.warnings.length || rowProblems(r).length) ? (
          <ul className="space-y-1 text-[12px]">
            {rows.flatMap((r, index) =>
              [...rowProblems(r), ...r.warnings].map((w, i) => (
                <li
                  key={`${r.key}-${i}`}
                  className={i < rowProblems(r).length ? "text-red" : "text-ink-2"}
                >
                  Row {index + 1}: {w}
                </li>
              )),
            )}
          </ul>
        ) : null}
      </div>
    </Modal>
  );
}
