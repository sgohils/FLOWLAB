import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Home from "./Home";
import { api } from "../api/client";

const { openDemo } = vi.hoisted(() => ({ openDemo: vi.fn() }));
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
    openDemo,
    replaceAnalysis: vi.fn(),
    clear: vi.fn(),
  }),
}));

// `restoreMocks: true` clears implementations between tests, so they are set
// per test rather than once at module scope.
beforeEach(() => {
  openDemo.mockResolvedValue(true);
  vi.mocked(api.meta).mockRejectedValue(new Error("offline"));
  vi.mocked(api.health).mockReturnValue(new Promise(() => {}));
  vi.mocked(api.analyses).mockResolvedValue([]);
});

function CurrentPath() {
  return <output data-testid="path">{useLocation().pathname}</output>;
}

it("scrolls to upload without navigating to a nonexistent route", () => {
  render(<MemoryRouter><Home /><CurrentPath /></MemoryRouter>);
  const upload = document.getElementById("upload")!;
  upload.scrollIntoView = vi.fn();
  fireEvent.click(screen.getByRole("button", { name: "Analyze Traffic Video" }));
  expect(upload.scrollIntoView).toHaveBeenCalled();
  expect(screen.getByTestId("path")).toHaveTextContent("/");
  expect(screen.getByRole("button", { name: "Choose video" })).toHaveFocus();
});

it("stays on Home and explains a failed demo request", async () => {
  openDemo.mockResolvedValue(false);
  render(<MemoryRouter><Home /><CurrentPath /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Try Sample Analysis" }));
  await screen.findByText(/demo could not be loaded/);
  expect(screen.getByTestId("path")).toHaveTextContent(/^\/$/);
});

it("opens the demo analysis after loading succeeds", async () => {
  render(<MemoryRouter><Home /><CurrentPath /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Try Sample Analysis" }));
  expect(await screen.findByText("/analysis/demo")).toBeInTheDocument();
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
    const subtitle = screen.getByText(/^The most recent saved analyses/);
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
