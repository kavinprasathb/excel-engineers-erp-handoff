import type { ReactNode } from "react";
import { Loading } from "../ui/Spinner";
import { ErrorState } from "../ui/ErrorState";
import { EmptyState } from "../ui/EmptyState";
import type { IconName } from "../ui/Icon";

export interface ListStatusProps {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  errorTitle: string;
  emptyTitle: string;
  emptyDescription?: string;
  emptyIcon?: IconName;
  emptyAction?: ReactNode;
}

/**
 * Loading, error and empty are three different answers and this is the one
 * place the app decides which of them it is looking at. Passed to DataList as
 * `message`, so a list never silently renders "no results" for a failed load.
 */
export function ListStatus({
  isPending,
  isError,
  error,
  onRetry,
  errorTitle,
  emptyTitle,
  emptyDescription,
  emptyIcon = "inbox",
  emptyAction,
}: ListStatusProps) {
  if (isPending) return <div className="p-4"><Loading /></div>;
  if (isError) {
    return (
      <div className="p-3">
        <ErrorState title={errorTitle} error={error} onRetry={onRetry} />
      </div>
    );
  }
  return (
    <EmptyState
      icon={emptyIcon}
      title={emptyTitle}
      description={emptyDescription}
      action={emptyAction}
    />
  );
}
