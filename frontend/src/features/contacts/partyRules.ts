/**
 * Client-side mirror of the backend's customer/supplier rules
 * (`backend/app/services/party.py`): GST number, city, state and pin code
 * are mandatory; the GST number is a GSTIN and the pin code six digits. The
 * server stays the authority; this only lets a field go red before submit.
 */

export const GSTIN_RE = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
export const PIN_RE = /^\d{6}$/;

export interface PartyFields {
  gstin: string;
  city: string;
  state: string;
  pincode: string;
}

export type PartyErrors = Partial<Record<keyof PartyFields, string>>;

/** The GST number as it is stored: no spaces, capitals. */
export function normaliseGstin(value: string): string {
  return value.replace(/\s+/g, "").toUpperCase();
}

export function partyErrors(v: PartyFields): PartyErrors {
  const errors: PartyErrors = {};
  const gstin = normaliseGstin(v.gstin);
  if (!gstin) errors.gstin = "Enter the GST number.";
  else if (!GSTIN_RE.test(gstin)) errors.gstin = "Enter a valid 15-character GST number, e.g. 33AAIFE2328P1Z9.";
  if (!v.city.trim()) errors.city = "Enter the city.";
  if (!v.state.trim()) errors.state = "Enter the state.";
  const pin = v.pincode.trim();
  if (!pin) errors.pincode = "Enter the pin code.";
  else if (!PIN_RE.test(pin)) errors.pincode = "A pin code is 6 digits.";
  return errors;
}

/** "Address line 1, City, State - 636016": what a document prints. */
export function formatAddress(line1: string, city: string, state: string, pincode: string): string {
  const place = [line1, city, state].map((p) => p.trim()).filter(Boolean).join(", ");
  return pincode.trim() ? `${place}${place ? " - " : ""}${pincode.trim()}` : place;
}
