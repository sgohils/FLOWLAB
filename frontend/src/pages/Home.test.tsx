import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Home from "./Home";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: { meta: vi.fn(), health: vi.fn(), analyses: vi.fn(), delete: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

vi.mock("../state/AnalysisContext", () => ({
  useAnalysis: () => ({
    analysisId: null,
    analysis: null,
    job: null,
    loading: false,
    error: null,
    load: vi.fn(),
    openDemo: vi.fn(),
    replaceAnalysis: vi.fn(),
    clear: vi.fn(),
  }),
}));

// `restoreMocks: true` clears implementations between tests, so they are set
// per test rather than once at module scope.
beforeEach(() => {
  vi.mocked(api.meta).mockRejectedValue(new Error("offline"));
  vi.mocked(api.health).mockReturnValue(new Promise(() => {}));
  vi.mocked(api.analyses).mockResolvedValue([]);
});

/**
 * The saved-analyses heading claimed "Everything already on this machine" while
 * the list behind it is one capped page. The wording is the defect, so it is
 * pinned here rather than left to a reviewer to notice.
 */
describe("Home, the saved analyses heading", () => {
  it("does not promise more than the list can show", () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    const subtitle = screen.getByText(/analyses already on this machine/);
    expect(subtitle).toBeInTheDocument();
    expect(screen.queryByText(/^Everything/)).not.toBeInTheDocument();
  });

  it("names the cap so the reader knows the list can be truncated", () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(screen.getByText(/up to 100 of them/)).toBeInTheDocument();
  });
});
