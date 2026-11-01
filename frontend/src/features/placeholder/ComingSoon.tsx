import { useLocation } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { EmptyState } from "../../components/ui/EmptyState";
import { Card } from "../../components/ui/Card";
import { NAV_ITEMS } from "../../components/layout/nav";

/**
 * The nav lists the whole product, not just what ships today. Rather than
 * hiding Quotations and Orders — which would make the app look like less than
 * it is — the unready routes land here and say so plainly.
 */
export default function ComingSoon() {
  const { pathname } = useLocation();
  const item = NAV_ITEMS.find((n) => n.to === pathname);
  const label = item?.label ?? "This section";

  return (
    <>
      <PageHeader title={label} />
      <PageBody>
        <Card>
          <EmptyState
            icon={item?.icon ?? "inbox"}
            title={`${label} is coming soon`}
            description="Inventory, Products and Suppliers are the parts of the system that work today."
          />
        </Card>
      </PageBody>
    </>
  );
}
