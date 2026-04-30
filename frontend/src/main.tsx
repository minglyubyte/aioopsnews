import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import DemoDashboard from "./demo/DemoDashboard";
import "./index.css";

const path = window.location.pathname;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {path === "/demo" ? <DemoDashboard /> : <App />}
  </React.StrictMode>,
);
