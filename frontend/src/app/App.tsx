import { Suspense, lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";

const DashboardPage = lazy(() =>
  import("../features/dashboard/DashboardPage").then((module) => ({ default: module.DashboardPage })),
);
const AccountsPage = lazy(() =>
  import("../features/accounts/AccountsPage").then((module) => ({ default: module.AccountsPage })),
);
const HoldingsPage = lazy(() =>
  import("../features/holdings/HoldingsPage").then((module) => ({ default: module.HoldingsPage })),
);
const InvestmentsPage = lazy(() =>
  import("../features/investments/InvestmentsPage").then((module) => ({ default: module.InvestmentsPage })),
);
const DesignSystemPage = lazy(() =>
  import("../features/design-system/DesignSystemPage").then((module) => ({
    default: module.DesignSystemPage,
  })),
);
const ReadswellPage = lazy(() =>
  import("../features/readswell/ReadswellPage").then((module) => ({ default: module.ReadswellPage })),
);
const SettingsPage = lazy(() =>
  import("../features/settings/SettingsPage").then((module) => ({ default: module.SettingsPage })),
);

function RouteFallback() {
  return <div className="panel">Loading page...</div>;
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/readswell"
          element={
            <Suspense fallback={<RouteFallback />}>
              <ReadswellPage />
            </Suspense>
          }
        />
        <Route element={<AppShell />}>
          <Route
            path="/"
            element={
              <Suspense fallback={<RouteFallback />}>
                <DashboardPage />
              </Suspense>
            }
          />
          <Route
            path="/accounts"
            element={
              <Suspense fallback={<RouteFallback />}>
                <AccountsPage />
              </Suspense>
            }
          />
          <Route
            path="/design-system"
            element={
              <Suspense fallback={<RouteFallback />}>
                <DesignSystemPage />
              </Suspense>
            }
          />
          <Route
            path="/holdings"
            element={
              <Suspense fallback={<RouteFallback />}>
                <HoldingsPage />
              </Suspense>
            }
          />
          <Route
            path="/investments"
            element={
              <Suspense fallback={<RouteFallback />}>
                <InvestmentsPage />
              </Suspense>
            }
          />
          <Route
            path="/settings"
            element={
              <Suspense fallback={<RouteFallback />}>
                <SettingsPage />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
