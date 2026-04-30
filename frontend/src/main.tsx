import React from "react";
import ReactDOM from "react-dom/client";
import DemoDashboard from "./demo/DemoDashboard";
import "./index.css";
import InternalReviewPage from "./pages/InternalReviewPage";
import PublicDashboardPage from "./pages/PublicDashboardPage";

export function RouteEntry() {
  const path = window.location.pathname;

  if (path === "/demo") {
    return <DemoDashboard />;
  }

  if (path === "/internal") {
    return <InternalReviewPage />;
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
