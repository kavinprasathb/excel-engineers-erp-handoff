import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Modal } from "../../components/ui/Modal";
import { Button } from "../../components/ui/Button";
import { Art } from "../../components/illustrations/Art";
import { SEVERITY_COLOR, SEVERITY_LABEL, useNotifications } from "./api";
import type { Severity } from "./api";

const KEY = "daily-notice-seen";
const SEVERITIES: readonly Severity[] = ["critical", "warning", "info"];

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

function seenToday(): boolean {
  try {
    return localStorage.getItem(KEY) === today();
  } catch {
    return false;
  }
}

function markSeen(): void {
  try {
    localStorage.setItem(KEY, today());
  } catch {
    // Private window or blocked storage: it will simply show again next load.
  }
}

/**
 * Once a day, the first time the app is opened, a summary of what is waiting.
 * Nothing to show, no popup.
 */
export function DailyNotice() {
  const navigate = useNavigate();
  const n = useNotifications();
  const [dismissed, setDismissed] = useState(seenToday);
  const open = !dismissed && (n.data?.total ?? 0) > 0;

  function close() {
    markSeen();
    setDismissed(true);
  }

  if (!n.data) return null;
  const top = n.data.items.slice(0, 5);
  return (
    <Modal
      open={open}
      onClose={close}
      title="Good day! Here is what needs doing"
      description={`${n.data.total} ${n.data.total === 1 ? "thing needs" : "things need"} attention today.`}
      footer={
        <>
          <Button onClick={close}>Later</Button>
          <Button
            variant="primary"
            onClick={() => {
              close();
              navigate("/notifications");
            }}
          >
            Open notifications
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="flex justify-center">
          <Art name="bell" size={84} />
        </div>
        <div className="grid grid-cols-3 gap-2">
          {SEVERITIES.map((s) => (
            <div key={s} className="rounded-lg border border-line p-2 text-center">
              <p className="text-xl font-semibold tabular-nums" style={{ color: SEVERITY_COLOR[s] }}>
                {n.data.counts[s]}
              </p>
              <p className="text-[11px] text-ink-2">{SEVERITY_LABEL[s]}</p>
            </div>
          ))}
        </div>
        <ul className="space-y-1.5 text-[13px]">
          {top.map((i) => (
            <li key={i.key} className="flex items-start gap-2">
              <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: SEVERITY_COLOR[i.severity] }} />
              <span className="text-ink">{i.title}</span>
            </li>
          ))}
        </ul>
        {n.data.total > top.length ? (
          <p className="text-[12px] text-ink-2">and {n.data.total - top.length} more.</p>
        ) : null}
      </div>
    </Modal>
  );
}
