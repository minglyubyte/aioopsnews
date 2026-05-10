import React from "react";
import ReactDOM from "react-dom/client";
import DemoDashboard from "./demo/DemoDashboard";
import "./index.css";
import InternalReviewPage from "./pages/InternalReviewPage";
import PublicDashboardPage from "./pages/PublicDashboardPage";
import PublicIncidentDetailPage from "./pages/PublicIncidentDetailPage";
import { parseIncidentIdFromPath } from "./lib/publicIncidentRoutes";

export function RouteEntry() {
  const path = window.location.pathname;
  const incidentId = parseIncidentIdFromPath(path);

  if (path === "/demo") {
    return <DemoDashboard />;
  }

  if (path === "/internal") {
    return <InternalReviewPage />;
  }

  if (incidentId) {
    return <PublicIncidentDetailPage incidentId={incidentId} />;
  }

  return <PublicDashboardPage />;
}

const rootElement = document.getElementById("root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <RouteEntry />
    </React.StrictMode>,
  );
}
