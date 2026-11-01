import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { FormField } from "../../components/ui/FormField";
import { Select } from "../../components/ui/Select";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { useToast } from "../../components/ui/toast-context";
import { errorMessage } from "../../lib/errors";
import {
  quotationPdfUrl,
  useQuotationChanges,
  useQuotationCompare,
  useQuotationLineChanges,
  useQuotationRevisions,
  useReviseQuotation,
} from "../quotations/api";
import { StatusBadge } from "../quotations/status";
import { STAGE_PATH, formatQuoteDate, formatRupees, stageLabel, stageOf } from "../quotations/format";
import type { QuotationChange, QuotationLineChange, QuotationSummary, VersionKind } from "../../api/types";

const LIST_LABEL = {
  quotation: "All quotations",
  revised: "All revised quotations",
  negotiation: "All negotiations",
} as const;

/** "R2" / "N1" / "R2N1" beside the full stage label, or "Original". */
function shortRef(r: QuotationSummary): string {
  return (r.rev_no ? `R${r.rev_no}` : "") + (r.neg_no ? `N${r.neg_no}` : "") || "Original";
}

/**
 * One quotation number, every version it went through, newest first: the
 * original, each revised quotation (R1, R2...) and each negotiation (N1,
 * N2...), each with what it changed against the version it was started from.
 * Any version can be opened, printed, compared with any other, or used to
 * start the next revision or negotiation. Earlier versions are never changed.
 */
export default function NegotiationHistoryPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const revisions = useQuotationRevisions(Number(id));
  const revise = useReviseQuotation();

  const rows = [...(revisions.data ?? [])].reverse();
  const latest = rows[0];
  const base = latest?.base_number ?? "";
  // Accepted is final for the whole number; the server enforces it too.
  const accepted = rows.find((r) => r.status === "accepted");

  function startFrom(r: QuotationSummary, kind: VersionKind) {
    revise.mutate(
      { id: r.id, kind },
      {
        onSuccess: (q) => {
          toast.success(`${stageLabel(q)} started as ${q.number}.`);
          navigate(`/quotations/${q.id}`);
        },
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  const listStage = latest ? stageOf(latest) : "negotiation";

  return (
    <>
      <PageHeader
        title={base ? `Quotation history · ${base}` : "Quotation history"}
        description={
          latest
            ? `${latest.customer.name} · ${
                accepted
                  ? `Accepted at ${stageLabel(accepted).toLowerCase()}`
                  : latest.status === "declined"
                    ? `Declined at ${stageLabel(latest).toLowerCase()}`
                    : `Now at ${stageLabel(latest).toLowerCase()} (${latest.number})`
              } · ${rows.length} ${rows.length === 1 ? "version" : "versions"}`
            : undefined
        }
        actions={
          <Button onClick={() => navigate(STAGE_PATH[listStage])}>{LIST_LABEL[listStage]}</Button>
        }
      />
      <PageBody>
        {revisions.isPending ? (
          <Loading />
        ) : revisions.isError ? (
          <ErrorState
            title="Could not load this history"
            error={revisions.error}
            onRetry={() => revisions.refetch()}
          />
        ) : (
          <div className="space-y-4">
            {rows.length > 1 ? <Compare versions={rows} /> : null}
            <ol className="space-y-3">
              {rows.map((r) => (
                <li key={r.id}>
                  <Card>
                    <CardBody className="space-y-3">
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                        <span className="text-[15px] font-semibold text-ink">{stageLabel(r)}</span>
                        <span className="tabular-nums text-ink-2">{r.number}</span>
                        <StatusBadge status={r.status} />
                        {r.id === latest?.id && r.status === "pending" ? (
                          <span className="text-[12px] font-medium text-brand">Current version</span>
                        ) : null}
                        <span className="text-[13px] text-ink-2">
                          {r.revision > 0 ? "Made" : "Quoted"} {formatQuoteDate(r.created_at.slice(0, 10))}
                        </span>
                        <span className="ml-auto text-[15px] font-semibold tabular-nums text-ink">
                          {formatRupees(r.total_paise)}
                        </span>
                      </div>
                      {r.revision > 0 ? (
                        <Changes id={r.id} />
                      ) : (
                        <p className="text-[13px] text-ink-2">The first offer sent to the customer.</p>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" onClick={() => navigate(`/quotations/${r.id}`)}>
                          Open
                        </Button>
                        <Button size="sm" onClick={() => window.open(quotationPdfUrl(r.id), "_blank")}>
                          PDF
                        </Button>
                        {accepted ? null : (
                          <>
                            <Button
                              size="sm"
                              disabled={revise.isPending}
                              title="Product, quantity or technical changes"
                              onClick={() => startFrom(r, "revision")}
                            >
                              Revise from this version
                            </Button>
                            <Button
                              size="sm"
                              disabled={revise.isPending}
                              title="Price only"
                              onClick={() => startFrom(r, "negotiation")}
                            >
                              Negotiate from this version
                            </Button>
                          </>
                        )}
                      </div>
                    </CardBody>
                  </Card>
                </li>
              ))}
            </ol>
          </div>
        )}
      </PageBody>
    </>
  );
}

/** Pick any two versions; see what changed from the first to the second. */
function Compare({ versions }: { versions: QuotationSummary[] }) {
  // Newest first on screen; default: the original against the latest.
  const [from, setFrom] = useState(String(versions[versions.length - 1].id));
  const [to, setTo] = useState(String(versions[0].id));
  const same = from === to;
  const result = useQuotationCompare(Number(to), Number(from));

  const options = versions.map((v) => (
    <option key={v.id} value={v.id}>
      {shortRef(v)} · {v.number} · {formatRupees(v.total_paise)}
    </option>
  ));

  return (
    <Card>
      <CardHeader
        title="Compare versions"
        description="Any two versions of this quotation: the original, revised quotations and negotiations."
      />
      <CardBody className="space-y-3">
        <div className="grid gap-4 md:grid-cols-2">
          <FormField label="From">
            {(p) => (
              <Select {...p} value={from} onChange={(e) => setFrom(e.target.value)}>
                {options}
              </Select>
            )}
          </FormField>
          <FormField label="To">
            {(p) => (
              <Select {...p} value={to} onChange={(e) => setTo(e.target.value)}>
                {options}
              </Select>
            )}
          </FormField>
        </div>
        {same ? (
          <p className="text-[13px] text-ink-2">Choose two different versions.</p>
        ) : result.isPending ? (
          <Loading />
        ) : result.isError ? (
          <ErrorState title="Could not compare" error={result.error} onRetry={() => result.refetch()} />
        ) : (
          <ChangeList lines={result.data.lines} changes={result.data.changes} empty="These two versions are the same." />
        )}
      </CardBody>
    </Card>
  );
}

function show(c: QuotationChange, v: string): string {
  if (c.field === "Rate" && /^\d+$/.test(v)) return formatRupees(Number(v));
  return v === "" ? "blank" : v;
}

function money(paise: number | null): string {
  return paise === null ? "—" : formatRupees(paise);
}

function qty(r: QuotationLineChange): string {
  if (r.old_quantity === null) return String(r.new_quantity);
  if (r.new_quantity === null) return String(r.old_quantity);
  return r.old_quantity === r.new_quantity ? String(r.new_quantity) : `${r.old_quantity} → ${r.new_quantity}`;
}

/** Old rate minus new rate, per unit. Positive is a discount given. */
function Discount({ r }: { r: QuotationLineChange }) {
  if (r.old_rate_paise === null || r.new_rate_paise === null) {
    return <span className="text-ink-2">{r.change === "added" ? "New item" : "Removed"}</span>;
  }
  const diff = r.old_rate_paise - r.new_rate_paise;
  if (diff === 0) return <span className="text-ink-2">No change</span>;
  const pct = r.old_rate_paise > 0 ? Math.round((Math.abs(diff) / r.old_rate_paise) * 1000) / 10 : null;
  const tone = diff > 0 ? "text-green" : "text-red";
  return (
    <span className={`font-medium ${tone}`}>
      {diff > 0 ? "−" : "+"}
      {formatRupees(Math.abs(diff))}
      {pct !== null ? <span className="ml-1 text-[12px] font-normal">({pct}%)</span> : null}
    </span>
  );
}

function Changes({ id }: { id: number }) {
  const lines = useQuotationLineChanges(id);
  const other = useQuotationChanges(id);
  if (lines.isPending || other.isPending) return <Loading />;
  return (
    <ChangeList
      lines={lines.data ?? []}
      changes={other.data ?? []}
      empty="No changes from the version it was started from."
    />
  );
}

function ChangeList({
  lines,
  changes,
  empty,
}: {
  lines: QuotationLineChange[];
  changes: QuotationChange[];
  empty: string;
}) {
  // Item rate/quantity changes are in the table; list only what it cannot show.
  const rest = changes.filter(
    (c) => !(c.section === "Items" && (c.field === "Rate" || c.field === "Quantity" || c.field === "Line")),
  );
  const rows = lines;
  return (
    <div className="space-y-3">
      {rows.length > 0 ? (
        <div className="overflow-x-auto rounded-md border border-line">
          <table className="w-full min-w-[560px] text-[13px]">
            <thead className="bg-hoverfill text-left text-[11px] font-medium uppercase tracking-wide text-ink-2">
              <tr>
                <th className="px-3 py-2">Description</th>
                <th className="px-3 py-2 text-right">Qty</th>
                <th className="px-3 py-2 text-right">Old rate</th>
                <th className="px-3 py-2 text-right">Discount</th>
                <th className="px-3 py-2 text-right">New rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((r, i) => (
                <tr key={i}>
                  <td className="px-3 py-2 text-ink">{r.description}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink">{qty(r)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-2">{money(r.old_rate_paise)}</td>
                  <td className="px-3 py-2 text-right tabular-nums"><Discount r={r} /></td>
                  <td className="px-3 py-2 text-right font-medium tabular-nums text-ink">{money(r.new_rate_paise)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {rest.length > 0 ? (
        <ul className="space-y-1 text-[13px]">
          {rest.map((c, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-ink-2">{c.section}</span>
              {c.item ? <span className="font-medium text-ink">{c.item}</span> : null}
              <span className="text-ink-2">{c.field}:</span>
              <span className="text-ink-2 line-through">{show(c, c.before)}</span>
              <span className="text-ink-2">→</span>
              <span className="font-medium text-ink">{show(c, c.after)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {rows.length === 0 && rest.length === 0 ? <p className="text-[13px] text-ink-2">{empty}</p> : null}
    </div>
  );
}
