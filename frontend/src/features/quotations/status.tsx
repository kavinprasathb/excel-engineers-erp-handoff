import { Badge } from "../../components/ui/Badge";
import type { BadgeTone } from "../../components/ui/Badge";
import type { QuotationStatus } from "../../api/types";
import { STATUS_LABEL } from "./format";

const TONE: Record<QuotationStatus, BadgeTone> = {
  pending: "amber",
  accepted: "green",
  declined: "red",
  superseded: "gray",
};

export function StatusBadge({ status }: { status: QuotationStatus }) {
  return <Badge tone={TONE[status]}>{STATUS_LABEL[status]}</Badge>;
}
