import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import LoginPage from "./features/auth/LoginPage";
import InventoryPage from "./features/inventory/InventoryPage";
import ProductsPage from "./features/products/ProductsPage";
import SuppliersPage from "./features/suppliers/SuppliersPage";
import CustomersPage from "./features/customers/CustomersPage";
import QuotationsPage from "./features/quotations/QuotationsPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import NegotiationsPage from "./features/negotiations/NegotiationsPage";
import RevisedQuotationsPage from "./features/negotiations/RevisedQuotationsPage";
import QuoteHistoryPage from "./features/history/QuoteHistoryPage";
import AnalyticsPage from "./features/analytics/AnalyticsPage";
import NotificationsPage from "./features/notifications/NotificationsPage";
import OrdersPage from "./features/orders/OrdersPage";
import OrderPage from "./features/orders/OrderPage";
import PurchaseOrdersPage from "./features/orders/PurchaseOrdersPage";
import PurchaseOrderPage from "./features/orders/PurchaseOrderPage";
import NegotiationHistoryPage from "./features/negotiations/NegotiationHistoryPage";
import QuotationEditorPage from "./features/quotations/QuotationEditorPage";
import SettingsPage from "./features/settings/SettingsPage";
import StaffPage from "./features/staff/StaffPage";
import DealTrackerPage from "./features/deal-tracker/DealTrackerPage";
import ActivityPage from "./features/activity/ActivityPage";
import { OwnerOnly } from "./features/auth/OwnerOnly";
import ComingSoon from "./features/placeholder/ComingSoon";
import { NAV_ITEMS } from "./components/layout/nav";
import { watchSystemTheme } from "./lib/theme";
import { PageBody, PageHeader } from "./components/layout/PageHeader";
import { Card } from "./components/ui/Card";
import { EmptyState } from "./components/ui/EmptyState";

export default function App() {
  // Keeps the theme correct when the OS flips while the app is open, but only
  // while the preference is "system". First paint is handled in index.html.
  useEffect(() => watchSystemTheme(), []);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          {/* The owner's first look of the day: where every offer stands. */}
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/quotations" element={<QuotationsPage />} />
          <Route path="/quotations/new" element={<QuotationEditorPage />} />
          <Route path="/quotations/:id" element={<QuotationEditorPage />} />
          <Route path="/revised-quotations" element={<RevisedQuotationsPage />} />
          <Route path="/negotiations" element={<NegotiationsPage />} />
          <Route path="/quote-history" element={<QuoteHistoryPage />} />
          <Route path="/analytics" element={<OwnerOnly title="Analytics"><AnalyticsPage /></OwnerOnly>} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/orders/:id" element={<OrderPage />} />
          <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
          <Route path="/purchase-orders/:id" element={<PurchaseOrderPage />} />
          <Route path="/negotiations/:id" element={<NegotiationHistoryPage />} />
          <Route path="/settings" element={<OwnerOnly title="Settings"><SettingsPage /></OwnerOnly>} />
          <Route path="/staff" element={<StaffPage />} />
          <Route path="/deal-tracker" element={<OwnerOnly title="Deal Tracker"><DealTrackerPage /></OwnerOnly>} />
          <Route path="/activity" element={<ActivityPage />} />

          {NAV_ITEMS.filter((item) => !item.ready).map((item) => (
            <Route key={item.to} path={item.to} element={<ComingSoon />} />
          ))}

          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  );
}

function NotFound() {
  return (
    <>
      <PageHeader title="Not found" />
      <PageBody>
        <Card>
          <EmptyState
            title="That page does not exist"
            description="Check the address, or pick a section from the navigation."
          />
        </Card>
      </PageBody>
    </>
  );
}
