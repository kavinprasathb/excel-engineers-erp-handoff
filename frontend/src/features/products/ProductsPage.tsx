import { useState } from "react";
import { PageBody, PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Icon } from "../../components/ui/Icon";
import { useListParams } from "../../lib/useListParams";
import { ProductsFilters } from "./components/ProductsFilters";
import { ProductsTable } from "./components/ProductsTable";
import { ProductFormDrawer } from "./components/ProductFormDrawer";
import { DeleteProductDialog } from "./components/DeleteProductDialog";
import { ImportDialog } from "../imports/ImportDialog";
import type { Product } from "../../api/types";
import { useIsOwner } from "../auth/api";

export default function ProductsPage() {
  // Import writes costs, so the server allows it to the owner only.
  const owner = useIsOwner();
  const params = useListParams();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [deleting, setDeleting] = useState<Product | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  function openCreate() {
    setEditing(null);
    setDrawerOpen(true);
  }

  function openEdit(product: Product) {
    setEditing(product);
    setDrawerOpen(true);
  }

  return (
    <>
      <PageHeader
        title="Products"
        description="The catalogue of pumps, spares and accessories."
        actions={
          <>
            {/* Import is the strong secondary: used once a quarter, but it is
                how the catalogue gets here in the first place. */}
            {owner ? (
              <Button variant="dark" onClick={() => setImportOpen(true)}>
                Import
              </Button>
            ) : null}
            <Button variant="primary" onClick={openCreate}>
              <Icon name="plus" size={15} />
              New product
            </Button>
          </>
        }
      />
      <PageBody>
        <ProductsFilters params={params} />
        <ProductsTable
          params={params}
          onEdit={openEdit}
          onDelete={setDeleting}
          onCreate={openCreate}
        />
      </PageBody>

      <ProductFormDrawer
        open={drawerOpen}
        product={editing}
        onClose={() => setDrawerOpen(false)}
      />
      <DeleteProductDialog product={deleting} onClose={() => setDeleting(null)} />
      <ImportDialog open={importOpen} onClose={() => setImportOpen(false)} />
    </>
  );
}
