import { useNavigate } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { useListParams } from "../../lib/useListParams";
import { QuotationsFilters } from "../quotations/components/QuotationsFilters";
import { QuotationsTable } from "../quotations/components/QuotationsTable";

/**
 * Every quotation whose latest version is a revised quotation (R1, R2...):
 * the customer asked for a product, quantity or technical change. One row
 * per number; a row opens the full history of that number.
 */
export default function RevisedQuotationsPage() {
  const params = useListParams();
  const navigate = useNavigate();

  return (
    <>
      <PageHeader
        title="Revised Quotations"
        description="Quotations revised for product, quantity or technical changes (R1, R2...). Open one to see every version."
      />
      <PageBody>
        <QuotationsFilters params={params} />
        <QuotationsTable
          params={params}
          stage="revised"
          onOpen={(q) => navigate(`/negotiations/${q.id}`)}
        />
      </PageBody>
    </>
  );
}
