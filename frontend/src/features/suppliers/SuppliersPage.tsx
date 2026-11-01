import { useState } from "react";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Icon } from "../../components/ui/Icon";
import { useListParams } from "../../lib/useListParams";
import { ImportContactsDialog } from "../contacts/ImportContactsDialog";
import { SuppliersFilters } from "./components/SuppliersFilters";
import { SuppliersTable } from "./components/SuppliersTable";
import { SupplierFormDrawer } from "./components/SupplierFormDrawer";
import { DeleteSupplierDialog } from "./components/DeleteSupplierDialog";
import type { Supplier } from "../../api/types";

export default function SuppliersPage() {
  const params = useListParams();
  // `null` inside an open drawer means "create"; the drawer being open at all
  // is the separate boolean, so editing and creating cannot be confused.
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [deleting, setDeleting] = useState<Supplier | null>(null);

  function openCreate() {
    setEditing(null);
    setDrawerOpen(true);
  }

  function openEdit(supplier: Supplier) {
    setEditing(supplier);
    setDrawerOpen(true);
  }

  return (
    <>
      <PageHeader
        title="Suppliers"
        description="Who you buy from."
        actions={
          <>
            <Button onClick={() => setImportOpen(true)}>Import</Button>
            <Button variant="primary" onClick={openCreate}>
              <Icon name="plus" size={15} />
              New supplier
            </Button>
          </>
        }
      />
      <PageBody>
        <SuppliersFilters params={params} />
        <SuppliersTable
          params={params}
          onEdit={openEdit}
          onDelete={setDeleting}
          onCreate={openCreate}
        />
      </PageBody>

      <SupplierFormDrawer
        open={drawerOpen}
        supplier={editing}
        onClose={() => setDrawerOpen(false)}
        onCreated={setEditing}
      />
      <DeleteSupplierDialog supplier={deleting} onClose={() => setDeleting(null)} />
      <ImportContactsDialog
        kind="suppliers"
        open={importOpen}
        onClose={() => setImportOpen(false)}
      />
    </>
  );
}
