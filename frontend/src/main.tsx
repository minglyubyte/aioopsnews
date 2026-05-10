import React from "react";
import ReactDOM from "react-dom/client";
import DemoDashboard from "./demo/DemoDashboard";
import "./index.css";
import InternalReviewPage from "./pages/InternalReviewPage";
import PublicDashboardPage from "./pages/PublicDashboardPage";
import PublicDisclaimerPage from "./pages/PublicDisclaimerPage";
import PublicIncidentDetailPage from "./pages/PublicIncidentDetailPage";
import PublicTopicPage from "./pages/PublicTopicPage";
import { parseIncidentIdFromPath } from "./lib/publicIncidentRoutes";
import { parseTopicRoute } from "./lib/publicTopicRoutes";

export function RouteEntry() {
  const path = window.location.pathname;
  const incidentId = parseIncidentIdFromPath(path);
  const topicRoute = parseTopicRoute(path);

  if (path === "/demo") {
    return <DemoDashboard />;
  }

  if (path === "/internal") {
    return <InternalReviewPage />;
  }

  if (path === "/disclaimer") {
    return <PublicDisclaimerPage />;
  }

  if (incidentId) {
    return <PublicIncidentDetailPage incidentId={incidentId} />;
  }

  if (topicRoute) {
    return <PublicTopicPage kind={topicRoute.kind} slug={topicRoute.slug} />;
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
