import { useState } from "react";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Icon } from "../../components/ui/Icon";
import { useListParams } from "../../lib/useListParams";
import { ImportContactsDialog } from "../contacts/ImportContactsDialog";
import { CustomersFilters } from "./components/CustomersFilters";
import { CustomersTable } from "./components/CustomersTable";
import { CustomerFormDrawer } from "./components/CustomerFormDrawer";
import { DeleteCustomerDialog } from "./components/DeleteCustomerDialog";
import type { Customer } from "../../api/types";

export default function CustomersPage() {
  const params = useListParams();
  // `null` inside an open drawer means "create"; the drawer being open at all
  // is the separate boolean, so editing and creating cannot be confused.
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState<Customer | null>(null);

  function openCreate() {
    setEditing(null);
    setDrawerOpen(true);
  }

  function openEdit(customer: Customer) {
    setEditing(customer);
    setDrawerOpen(true);
  }

  return (
    <>
      <PageHeader
        title="Customers"
        description="Who you quote to."
        actions={
          <>
            <Button onClick={() => setImportOpen(true)}>Import</Button>
            <Button variant="primary" onClick={openCreate}>
              <Icon name="plus" size={15} />
              New customer
            </Button>
          </>
        }
      />
      <PageBody>
        <CustomersFilters params={params} />
        <CustomersTable
          params={params}
          onEdit={openEdit}
          onDelete={setDeleting}
          onCreate={openCreate}
        />
      </PageBody>

      <CustomerFormDrawer
        open={drawerOpen}
        customer={editing}
        onClose={() => setDrawerOpen(false)}
        onCreated={setEditing}
      />
      <DeleteCustomerDialog customer={deleting} onClose={() => setDeleting(null)} />
      <ImportContactsDialog
        kind="customers"
        open={importOpen}
        onClose={() => setImportOpen(false)}
      />
    </>
  );
}
