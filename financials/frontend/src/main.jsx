import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App.jsx";
import "./index.css";

// One palette since 0.20.0, so there is nothing to apply before paint. Light
// and dark still follow the system through Tailwind's `darkMode: "media"`.
try {
  localStorage.removeItem("financials.theme");
} catch {
  /* private mode — the leftover key is harmless either way */
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
