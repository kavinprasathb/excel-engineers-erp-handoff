import { errorMessage } from "../../lib/errors";
import { Button } from "./Button";
import { Icon } from "./Icon";
import { errorCardCls } from "./styles";

/** Says what failed rather than "something went wrong", and offers a retry. */
export function ErrorState({
  title = "Could not load this",
  error,
  onRetry,
}: {
  title?: string;
  error?: unknown;
  onRetry?: () => void;
}) {
  return (
    <div className={errorCardCls} role="alert">
      <div className="flex items-start gap-2.5">
        <Icon name="alert" className="mt-0.5 text-red" />
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-red">{title}</p>
          <p className="mt-0.5 text-[13px] text-ink-2">{errorMessage(error)}</p>
          {onRetry ? (
            <Button size="sm" onClick={onRetry} className="mt-3">
              <Icon name="refresh" size={15} />
              Retry
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
