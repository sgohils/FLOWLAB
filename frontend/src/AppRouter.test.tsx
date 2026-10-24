import { render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";
import { AppRouter, restoreLegacyRoute } from "./AppRouter";

afterEach(() => { window.history.replaceState(null, "", "/"); });

function renderRoutes() {
  render(<AppRouter><Routes>
    <Route path="/analysis/demo" element={<h1>Demo analysis</h1>} />
    <Route path="/simulation/demo" element={<h1>Demo simulation</h1>} />
    <Route path="*" element={<h1>Not found</h1>} />
  </Routes></AppRouter>);
}

it("opens a public analysis deep link without requiring a hash route", () => {
  window.history.replaceState(null, "", "/analysis/demo");
  restoreLegacyRoute();
  renderRoutes();
  expect(screen.getByRole("heading")).toHaveTextContent("Demo analysis");
});

it("opens a public simulation deep link on reload", () => {
  window.history.replaceState(null, "", "/simulation/demo");
  renderRoutes();
  expect(screen.getByRole("heading")).toHaveTextContent("Demo simulation");
});

it("preserves bookmarks from the old hash router, including query strings", () => {
  window.history.replaceState(null, "", "/#/analysis/demo?tab=queue");
  restoreLegacyRoute();
  renderRoutes();
  expect(window.location.pathname).toBe("/analysis/demo");
  expect(window.location.search).toBe("?tab=queue");
  expect(screen.getByRole("heading")).toHaveTextContent("Demo analysis");
});

it("keeps ordinary page anchors out of the route", () => {
  window.history.replaceState(null, "", "/analysis/demo#main-content");
  restoreLegacyRoute();
  renderRoutes();
  expect(screen.getByRole("heading")).toHaveTextContent("Demo analysis");
});
