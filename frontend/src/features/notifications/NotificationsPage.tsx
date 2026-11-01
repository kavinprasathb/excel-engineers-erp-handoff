import { Link } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Icon } from "../../components/ui/Icon";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { EmptyState } from "../../components/ui/EmptyState";
import { cardCls, eyebrowCls } from "../../components/ui/styles";
import { useListParams } from "../../lib/useListParams";
import { useToast } from "../../components/ui/toast-context";
import { CATEGORY_LABEL, SEVERITY_COLOR, SEVERITY_LABEL, useNotifications } from "./api";
import type { NotificationCategory, Severity } from "./api";

const CATEGORIES = Object.keys(CATEGORY_LABEL) as NotificationCategory[];
const SEVERITIES: readonly Severity[] = ["critical", "warning", "info"];

/**
 * Everything that needs someone to act, most urgent first. Each item goes away
 * by itself once the work is done, so this page empty means nothing is waiting.
 */
export default function NotificationsPage() {
  const params = useListParams();
  const n = useNotifications();
  const toast = useToast();
  const category = CATEGORIES.find((c) => c === params.get("category"));
  const severity = SEVERITIES.find((s) => s === params.get("severity"));

  return (
    <>
      <PageHeader
        title="Notifications"
        description="What needs doing today: quote replies, orders, purchase orders, and stock. Each one clears once it is done."
        actions={
          <Button
            loading={n.isFetching}
            onClick={async () => {
              const r = await n.refetch();
              if (r.isError) toast.error("Could not check. Please try again.");
              else {
                const total = r.data?.total ?? 0;
                toast.success(total === 0 ? "Checked just now. All clear." : `Checked just now. ${total} ${total === 1 ? "thing needs" : "things need"} attention.`);
              }
            }}
          >
            <Icon name="refresh" size={15} />
            Check again
          </Button>
        }
      />
      <PageBody>
        {n.isPending ? (
          <Loading />
        ) : n.isError ? (
          <ErrorState title="Could not load notifications" error={n.error} onRetry={() => n.refetch()} />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {SEVERITIES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => params.set({ severity: severity === s ? "" : s })}
                  className={`relative overflow-hidden p-4 text-left transition-colors hover:bg-hoverfill ${cardCls} ${severity === s ? "ring-2 ring-brand" : ""}`}
                >
                  <div aria-hidden className="pointer-events-none absolute -right-8 -top-10 size-32 rounded-full opacity-[0.16] blur-2xl" style={{ background: SEVERITY_COLOR[s] }} />
                  <p className={eyebrowCls}>{SEVERITY_LABEL[s]}</p>
                  <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink">{n.data.counts[s]}</p>
                  <p className="text-[12px] text-ink-2">
                    {s === "critical"
                      ? "Money or a customer at risk"
                      : s === "warning"
                        ? "Late or running low — act today"
                        : "Ready for the next step"}
                  </p>
                </button>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Chip active={!category} onClick={() => params.set({ category: "" })}>
                All · {n.data.total}
              </Chip>
              {CATEGORIES.map((c) => (
                <Chip key={c} active={category === c} onClick={() => params.set({ category: c })}>
                  {CATEGORY_LABEL[c]} · {n.data.by_category[c] ?? 0}
                </Chip>
              ))}
            </div>

            <List category={category} severity={severity} />
          </div>
        )}
      </PageBody>
    </>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-[13px] transition-colors ${
        active ? "border-brand bg-brand text-white" : "border-line bg-card text-ink hover:bg-hoverfill"
      }`}
    >
      {children}
    </button>
  );
}

function List({ category, severity }: { category?: NotificationCategory; severity?: Severity }) {
  const n = useNotifications();
  const items = (n.data?.items ?? []).filter(
    (i) => (!category || i.category === category) && (!severity || i.severity === severity),
  );
  if (items.length === 0) {
    return (
      <EmptyState
        icon="check"
        title={n.data?.total ? "Nothing here" : "All clear"}
        description={n.data?.total ? "Nothing matches this filter." : "Nothing is waiting on anyone. Well done."}
      />
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((i) => (
        <li key={i.key}>
          <Link
            to={i.link}
            className={`flex items-start gap-3 overflow-hidden border-l-4 p-3 transition-colors hover:bg-hoverfill ${cardCls}`}
            style={{ borderLeftColor: SEVERITY_COLOR[i.severity] }}
          >
            <span
              className="mt-0.5 rounded-full px-2 py-0.5 text-[11px] font-medium text-card"
              style={{ background: SEVERITY_COLOR[i.severity] }}
            >
              {SEVERITY_LABEL[i.severity]}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium text-ink">{i.title}</p>
              <p className="text-[12px] text-ink-2">{i.detail}</p>
            </div>
            <span className="hidden shrink-0 text-[12px] text-ink-2 sm:inline">{CATEGORY_LABEL[i.category]}</span>
            <Icon name="chevronRight" size={16} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
