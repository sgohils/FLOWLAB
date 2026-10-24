import type { ReactNode } from "react";
import { BrowserRouter, HashRouter } from "react-router-dom";

/** Keep bookmarks made by older builds working after switching to public paths. */
export function restoreLegacyRoute() {
  if (window.location.protocol !== "file:" && window.location.hash.startsWith("#/")) {
    window.history.replaceState(
      window.history.state, "", window.location.hash.slice(1),
    );
  }
}

export function AppRouter({ children }: { children: ReactNode }) {
  // HTTP deployments have SPA rewrites. Offline file previews still need hashes.
  const Router = window.location.protocol === "file:" ? HashRouter : BrowserRouter;
  return <Router>{children}</Router>;
}
