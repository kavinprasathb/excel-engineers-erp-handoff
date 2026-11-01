/**
 * Client-side mirror of the backend's email/phone rules
 * (`backend/app/schemas/contacts.py`): trimmed, blanks dropped, at most 10.
 * The server stays the authority; this only lets a row go red before submit.
 */

export const MAX_CONTACTS = 10;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const PHONE_RE = /^[0-9+\-() ]{7,20}$/;

export type ContactKind = "email" | "phone";

export function contactError(kind: ContactKind, raw: string): string | undefined {
  const value = kind === "phone" ? raw.trim().replace(/\s+/g, " ") : raw.trim();
  if (!value) return undefined;
  if (kind === "email") {
    return EMAIL_RE.test(value) ? undefined : "Enter a valid email address.";
  }
  return PHONE_RE.test(value)
    ? undefined
    : "7–20 characters: digits, spaces, +, - and brackets only.";
}

/** Trim, drop blanks, dedupe — what is sent to the server. */
export function cleanContacts(kind: ContactKind, values: readonly string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of values) {
    const value = kind === "phone" ? raw.trim().replace(/\s+/g, " ") : raw.trim();
    if (!value) continue;
    const key = kind === "phone" ? value.replace(/\D/g, "") : value.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(value);
  }
  return out;
}

export function hasContactErrors(kind: ContactKind, values: readonly string[]): boolean {
  return values.some((v) => contactError(kind, v) !== undefined);
}

/** "a@x.in, b@x.in" → ["a@x.in", "b@x.in"]; also splits on ; / and newlines. */
export function splitContacts(text: string): string[] {
  return text
    .split(/[,;/\n]+/)
    .map((v) => v.trim())
    .filter(Boolean);
}
