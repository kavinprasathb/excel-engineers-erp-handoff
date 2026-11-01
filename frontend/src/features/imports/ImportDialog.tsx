import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Modal } from "../../components/ui/Modal";
import { Button } from "../../components/ui/Button";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { DataList } from "../../components/ui/DataList";
import type { Column } from "../../components/ui/DataList";
import { Badge } from "../../components/ui/Badge";
import { Icon } from "../../components/ui/Icon";
import { errorCardCls, eyebrowCls, inputSizedCls } from "../../components/ui/styles";
import { errorMessage } from "../../lib/errors";
import { formatNumber, orDash } from "../../lib/format";
import { queryKeys } from "../../api/queryKeys";
import { IMPORT_TEMPLATE_URL, isTerminal, useImportJob, useStartImport } from "./api";
import type { ImportJob, ImportRowError } from "../../api/types";

const errorColumns: readonly Column<ImportRowError>[] = [
  { key: "row", header: "Row", numeric: true, cell: (e) => formatNumber(e.row), primary: true },
  { key: "column", header: "Column", cell: (e) => orDash(e.column) },
  { key: "value", header: "Value", cell: (e) => orDash(e.value) },
  { key: "message", header: "Problem", cell: (e) => e.message },
];

export function ImportDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const start = useStartImport();
  const [jobId, setJobId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const job = useImportJob(jobId);

  const data = job.data;
  const finished = isTerminal(data?.status);

  // The catalogue and every stock figure derived from it are stale the moment
  // the job lands. Done once, keyed on the job, so a late re-render cannot
  // start an invalidation loop.
  const invalidatedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!data || !isTerminal(data.status)) return;
    if (invalidatedFor.current === data.id) return;
    invalidatedFor.current = data.id;
    client.invalidateQueries({ queryKey: queryKeys.products.all });
    client.invalidateQueries({ queryKey: queryKeys.inventory.all });
  }, [data, client]);

  function close() {
    setJobId(null);
    setFile(null);
    start.reset();
    onClose();
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title="Import products"
      description="Upload the spreadsheet your supplier or Tally export produced."
      footer={
        <>
          <Button onClick={close}>{finished ? "Close" : "Cancel"}</Button>
          {jobId === null ? (
            <Button
              variant="primary"
              disabled={file === null}
              loading={start.isPending}
              onClick={() => {
                if (!file) return;
                start.mutate(file, { onSuccess: (created) => setJobId(created.id) });
              }}
            >
              Start import
            </Button>
          ) : null}
        </>
      }
    >
      {jobId === null ? (
        <div className="space-y-4">
          <div>
            <label htmlFor="import-file" className="mb-1.5 block text-xs font-medium text-ink-2">
              Spreadsheet
            </label>
            <input
              id="import-file"
              type="file"
              accept=".xlsx,.xls,.csv"
              className={inputSizedCls}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <p className="text-[13px] text-ink-2">
            Headers are detected automatically, so the sheet does not have to start on row one.
            Columns we do not recognise are listed after the run rather than dropped silently.
          </p>

          <a
            href={IMPORT_TEMPLATE_URL}
            download
            className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand transition-colors hover:underline"
          >
            <Icon name="products" size={15} />
            Download the template
          </a>

          {start.isError ? (
            <div className={errorCardCls} role="alert">
              <p className="text-[13px] font-medium text-red">Could not start the import</p>
              <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(start.error)}</p>
            </div>
          ) : null}
        </div>
      ) : (
        <ImportProgress job={data} isPending={job.isPending} error={job.error} isError={job.isError} />
      )}
    </Modal>
  );
}

function ImportProgress({
  job,
  isPending,
  isError,
  error,
}: {
  job: ImportJob | undefined;
  isPending: boolean;
  isError: boolean;
  error: unknown;
}) {
  if (isError) {
    return (
      <div className={errorCardCls} role="alert">
        <p className="text-[13px] font-medium text-red">Lost track of this import</p>
        <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(error)}</p>
      </div>
    );
  }

  if (isPending || !job) {
    return (
      <p role="status" className="text-[13px] text-ink-2">
        Loading…
      </p>
    );
  }

  const finished = isTerminal(job.status);
  // total_rows is 0 until header detection finishes. A determinate bar stuck
  // at 0% reads as "hung"; an indeterminate one reads as "counting".
  const counting = job.total_rows === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <p className="min-w-0 truncate text-[13px] font-medium text-ink">{job.filename}</p>
        <StatusBadge job={job} />
      </div>

      {finished ? null : (
        <ProgressBar
          label={
            counting
              ? "Reading the file…"
              : `${formatNumber(job.processed_rows)} of ${formatNumber(job.total_rows)} rows`
          }
          value={counting ? undefined : job.processed_rows}
          max={counting ? undefined : job.total_rows}
        />
      )}

      {job.message ? <p className="text-[13px] text-ink-2">{job.message}</p> : null}

      {finished ? (
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Figure label="Created" value={job.created_count} />
          <Figure label="Updated" value={job.updated_count} />
          <Figure label="Skipped" value={job.skipped_count} />
          <Figure label="Errors" value={job.error_count} tone={job.error_count > 0 ? "red" : "ink"} />
        </dl>
      ) : null}

      {/*
        The list that turns "the client's Tally export does not import" into a
        five-minute change: it names the headers we ignored, so the mapping can
        be extended against real column names instead of guesses.
      */}
      {finished ? (
        <section>
          <h3 className={eyebrowCls}>Unmapped columns</h3>
          {job.unmapped_headers.length === 0 ? (
            <p className="mt-1.5 text-[13px] text-ink-2">
              Every column in the sheet was recognised.
            </p>
          ) : (
            <>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {job.unmapped_headers.map((header) => (
                  <li
                    key={header}
                    className="rounded-full bg-hoverfill px-2 py-0.5 text-[11px] font-medium text-ink-2"
                  >
                    {header}
                  </li>
                ))}
              </ul>
              <p className="mt-1.5 text-[13px] text-ink-2">
                These were read but not imported, because nothing in the product record
                corresponds to them yet.
              </p>
            </>
          )}
        </section>
      ) : null}

      {job.errors.length > 0 ? (
        <section>
          <h3 className={eyebrowCls}>Rows that failed</h3>
          {job.error_count > job.errors.length ? (
            <p className="mt-1.5 text-[13px] text-ink-2">
              Showing the first {formatNumber(job.errors.length)} of{" "}
              {formatNumber(job.error_count)} errors.
            </p>
          ) : null}
          <div className="mt-2">
            <DataList
              columns={errorColumns}
              rows={job.errors}
              rowKey={(e) => `${e.row}-${e.column}`}
            />
          </div>
        </section>
      ) : null}
    </div>
  );
}

function StatusBadge({ job }: { job: ImportJob }) {
  if (job.status === "completed") return <Badge tone="green">Completed</Badge>;
  if (job.status === "failed") return <Badge tone="red">Failed</Badge>;
  if (job.status === "running") return <Badge tone="brand">Running</Badge>;
  return <Badge tone="gray">Queued</Badge>;
}

function Figure({
  label,
  value,
  tone = "ink",
}: {
  label: string;
  value: number;
  tone?: "ink" | "red";
}) {
  return (
    <div className="rounded-lg border border-line p-3">
      <dt className={eyebrowCls}>{label}</dt>
      <dd
        className={`mt-1 text-[15px] font-semibold tabular-nums ${
          tone === "red" ? "text-red" : "text-ink"
        }`}
      >
        {formatNumber(value)}
      </dd>
    </div>
  );
}
