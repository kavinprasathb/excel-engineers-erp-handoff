import type { ReactNode } from "react";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { EmptyState } from "../../components/ui/EmptyState";
import { useIsOwner, useMe } from "./api";

/** Wraps an owner-only page. The server refuses staff anyway; this says so kindly. */
export function OwnerOnly({ title, children }: { title: string; children: ReactNode }) {
  const me = useMe();
  const owner = useIsOwner();
  if (me.isPending) return null;
  if (owner) return <>{children}</>;
  return (
    <>
      <PageHeader title={title} />
      <PageBody>
        <EmptyState icon="lock" title="Only the owner can open this page" description="Ask the owner if you need something from here." />
      </PageBody>
    </>
  );
}
