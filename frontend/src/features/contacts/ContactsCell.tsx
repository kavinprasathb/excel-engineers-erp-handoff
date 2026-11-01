import { orDash } from "../../lib/format";

/** First value, then a "+N" chip carrying the rest in its tooltip. */
export function ContactsCell({ values, fallback }: { values: readonly string[]; fallback: string }) {
  const list = values.length ? values : fallback ? [fallback] : [];
  if (!list.length) return <>{orDash("")}</>;
  const rest = list.slice(1);
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5" title={list.join("\n")}>
      <span className="truncate">{list[0]}</span>
      {rest.length ? (
        <span className="shrink-0 rounded-full bg-hoverfill px-1.5 py-0.5 text-[11px] font-medium text-ink-2">
          +{rest.length}
        </span>
      ) : null}
    </span>
  );
}
