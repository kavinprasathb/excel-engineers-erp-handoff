import { useNavigate } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { useListParams } from "../../lib/useListParams";
import { QuotationsFilters } from "../quotations/components/QuotationsFilters";
import { QuotationsTable } from "../quotations/components/QuotationsTable";

/**
 * Every quotation now in price negotiation, one row per number at its latest
 * version. A row opens the full history of that number.
 */
export default function NegotiationsPage() {
  const params = useListParams();
  const navigate = useNavigate();

  return (
    <>
      <PageHeader
        title="Negotiations"
        description="Quotations in price negotiation (N1, N2...). Open one to see every version."
      />
      <PageBody>
        <QuotationsFilters params={params} />
        <QuotationsTable
          params={params}
          stage="negotiation"
          onOpen={(q) => navigate(`/negotiations/${q.id}`)}
        />
      </PageBody>
    </>
  );
}
