import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App.jsx";
import "./index.css";

// Applied before the first paint from a local cache, then reconciled with the
// stored setting. Waiting for the API would show the wrong palette for a beat
// on every load.
try {
  const cached = localStorage.getItem("financials.theme");
  if (cached && cached !== "default") document.documentElement.dataset.theme = cached;
} catch {
  /* private mode — the theme still applies once the API answers */
}

// HashRouter, not BrowserRouter: under Ingress the path prefix is dynamic and
// the server would have to know every client route to serve the shell.
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>
);
