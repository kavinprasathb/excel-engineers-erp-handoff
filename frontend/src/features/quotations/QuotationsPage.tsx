import { useNavigate } from "react-router-dom";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Icon } from "../../components/ui/Icon";
import { useListParams } from "../../lib/useListParams";
import { QuotationsFilters } from "./components/QuotationsFilters";
import { QuotationsTable } from "./components/QuotationsTable";

export default function QuotationsPage() {
  const params = useListParams();
  const navigate = useNavigate();

  return (
    <>
      <PageHeader
        title="Quotations"
        description="Offers sent to customers, every revision kept."
        actions={
          <Button variant="primary" onClick={() => navigate("/quotations/new")}>
            <Icon name="plus" size={15} />
            New quotation
          </Button>
        }
      />
      <PageBody>
        <QuotationsFilters params={params} />
        <QuotationsTable
          params={params}
          onOpen={(q) => navigate(`/quotations/${q.id}`)}
          onCreate={() => navigate("/quotations/new")}
        />
      </PageBody>
    </>
  );
}
