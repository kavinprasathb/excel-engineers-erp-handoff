import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Select } from "../../components/ui/Select";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Pagination } from "../../components/ui/Pagination";
import { Loading } from "../../components/ui/Spinner";
import { ErrorState } from "../../components/ui/ErrorState";
import { EmptyState } from "../../components/ui/EmptyState";
import { SearchInput } from "../../components/common/SearchInput";
import { FilterBar, FilterExtras } from "../../components/common/FilterBar";
import { cardCls } from "../../components/ui/styles";
import { api } from "../../api/client";
import type { Page } from "../../api/types";
import { useListParams } from "../../lib/useListParams";
import { OwnerOnly } from "../auth/OwnerOnly";
import { useStaff } from "../staff/api";

interface Activity {
  id: number;
  created_at: string;
  user_id: number | null;
  user_name: string;
  action: string;
  area: string;
  link: string;
  ip: string;
}

const AREAS = ["Quotations", "Orders", "Purchase orders", "Products", "Customers", "Suppliers", "Settings", "Staff", "Sign-in"];
const KEYS = ["q", "user", "area", "from", "to"] as const;

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ActivityPage() {
  return (
    <OwnerOnly title="Activity Log">
      <ActivityLog />
    </OwnerOnly>
  );
}

/** Who changed what, and when. Newest first. */
function ActivityLog() {
  const params = useListParams();
  const staff = useStaff();
  const filters = {
    q: params.get("q") || undefined,
    user_id: params.get("user") || undefined,
    area: params.get("area") || undefined,
    from: params.get("from") || undefined,
    to: params.get("to") || undefined,
    page: params.page,
  };
  const log = useQuery({
    meta: { silent: true },
    queryKey: ["activity", filters],
    queryFn: ({ signal }) => api.get<Page<Activity>>("/activity", filters, signal),
  });
  const filtered = params.hasFilters(KEYS);

  return (
    <>
      <PageHeader title="Activity Log" description="Every change made in the app: who did it, what, and when." />
      <PageBody>
        <FilterBar label="Activity filters">
          <SearchInput label="Search activity" placeholder="What happened, or who" value={params.get("q")} onCommit={(q) => params.set({ q })} />
          <Select aria-label="Person" value={params.get("user")} onChange={(e) => params.set({ user: e.target.value })}>
            <option value="">Everyone</option>
            {(staff.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name || u.email}
              </option>
            ))}
          </Select>
          <Select aria-label="Area" value={params.get("area")} onChange={(e) => params.set({ area: e.target.value })}>
            <option value="">All areas</option>
            {AREAS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </Select>
          <div className="flex items-center gap-2">
            <Input type="date" aria-label="From date" value={params.get("from")} onChange={(e) => params.set({ from: e.target.value })} />
            <span className="text-[13px] text-ink-2">to</span>
            <Input type="date" aria-label="To date" value={params.get("to")} onChange={(e) => params.set({ to: e.target.value })} />
          </div>
          <div className="sm:col-span-2 lg:col-span-4">
            <FilterExtras>
              {filtered ? (
                <Button size="sm" onClick={() => params.clear(KEYS)}>
                  Clear filters
                </Button>
              ) : null}
            </FilterExtras>
          </div>
        </FilterBar>

        {log.isPending ? (
          <Loading />
        ) : log.isError ? (
          <ErrorState title="Could not load the activity log" error={log.error} onRetry={() => log.refetch()} />
        ) : log.data.items.length === 0 ? (
          <EmptyState icon="inbox" title="Nothing here" description={filtered ? "Nothing matches these filters." : "Changes appear here as people use the app."} />
        ) : (
          <>
            <ul className={`divide-y divide-line ${cardCls}`}>
              {log.data.items.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-[13px]">
                  <span className="w-40 shrink-0 tabular-nums text-ink-2">{when(a.created_at)}</span>
                  <span className="w-32 shrink-0 truncate font-medium text-ink">{a.user_name || "—"}</span>
                  <span className="min-w-0 flex-1 text-ink">
                    {a.link ? (
                      <Link to={a.link} className="hover:underline">
                        {a.action}
                      </Link>
                    ) : (
                      a.action
                    )}
                  </span>
                  <span className="shrink-0 text-[12px] text-ink-2">{a.area}</span>
                </li>
              ))}
            </ul>
            <div className="mt-3">
              <Pagination page={log.data.page} pages={log.data.pages} total={log.data.total} pageSize={log.data.page_size} onPageChange={params.setPage} />
            </div>
          </>
        )}
      </PageBody>
    </>
  );
}
