import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppRouter, restoreLegacyRoute } from "./AppRouter";
import App from "./App";
import "./index.css";

restoreLegacyRoute();
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppRouter>
      <App />
    </AppRouter>
  </StrictMode>,
);
