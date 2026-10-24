import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecentAnalyses } from "./RecentAnalyses";
import { ApiError, api } from "../api/client";
import type { AnalysisListItem } from "../types";

vi.mock("../api/client", () => ({
  api: { analyses: vi.fn(), delete: vi.fn() },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status = 500) {
      super(message);
      this.status = status;
    }
  },
}));

const analysesMock = vi.mocked(api.analyses);
const deleteMock = vi.mocked(api.delete);

function item(overrides: Partial<AnalysisListItem> = {}): AnalysisListItem {
  return {
    analysis_id: "a1",
    filename: "gate.mp4",
    source: "upload",
    status: "complete",
    created_at: 1_700_000_000,
    duration: 42,
    vehicles_tracked: 12,
    peak_queue: 3,
    throughput_per_minute: 4.5,
    ...overrides,
  } as AnalysisListItem;
}

/** Renders the list inside a router, with a destination to navigate to. */
function renderList(currentId: string | null = null) {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<RecentAnalyses currentId={currentId} />} />
        <Route path="/analysis/:id" element={<h1>opened</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  analysesMock.mockReset();
  deleteMock.mockReset();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("RecentAnalyses", () => {
  it("asks for a full page rather than the endpoint default", async () => {
    analysesMock.mockResolvedValue([item()]);
    renderList();
    await screen.findByText("gate.mp4");
    expect(analysesMock).toHaveBeenCalledWith(100);
  });

  it("says the list is the most recent 100, not everything", async () => {
    analysesMock.mockResolvedValue([item()]);
    renderList();
    await screen.findByText("gate.mp4");
    expect(screen.getByText(/most recent analyses in the local database/)).toBeInTheDocument();
    expect(screen.queryByText(/Everything already on this machine/)).not.toBeInTheDocument();
  });

  it("announces that it is loading", async () => {
    analysesMock.mockReturnValue(new Promise(() => {}));
    renderList();
    expect(screen.getByRole("status")).toHaveTextContent("Loading saved analyses");
  });

  it("explains an empty machine rather than showing a blank panel", async () => {
    analysesMock.mockResolvedValue([]);
    renderList();
    expect(await screen.findByText(/Nothing stored on this machine yet/)).toBeInTheDocument();
  });

  it("announces a failure to list, politely", async () => {
    analysesMock.mockRejectedValue(new ApiError("the database is locked", 503));
    renderList();
    const notice = await screen.findByText("The saved analyses could not be listed");
    expect(notice).toBeInTheDocument();
    const status = screen.getAllByRole("status");
    expect(
      status.some((node) => node.textContent?.includes("the database is locked")),
    ).toBe(true);
    expect(status[0]).toHaveAttribute("aria-live", "polite");
  });

  it("opens an analysis when it is reopened", async () => {
    analysesMock.mockResolvedValue([item()]);
    renderList();
    await userEvent.click(await screen.findByRole("button", { name: "Reopen" }));
    expect(await screen.findByRole("heading", { name: "opened" })).toBeInTheDocument();
  });

  it("names the open analysis instead of offering to reopen it", async () => {
    analysesMock.mockResolvedValue([item()]);
    renderList("a1");
    await screen.findByText("gate.mp4");
    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument();
  });

  it("does not offer a peak queue for an analysis still being processed", async () => {
    analysesMock.mockResolvedValue([item({ status: "processing" })]);
    renderList();
    await screen.findByText("gate.mp4");
    expect(screen.getAllByText("processing").length).toBe(2);
    expect(screen.getByRole("button", { name: "Watch" })).toBeInTheDocument();
  });

  it("survives a filename far longer than the row it sits in", async () => {
    const long = `${"very-long-segment-".repeat(12)}clip.mp4`;
    analysesMock.mockResolvedValue([item({ filename: long })]);
    renderList();
    expect(await screen.findByText(long)).toBeInTheDocument();
  });

  it("does not claim the open analysis is being processed when it is not", async () => {
    // A stale id left over from a deleted record must not blank the numbers.
    analysesMock.mockResolvedValue([item({ analysis_id: "gone", status: "complete" })]);
    renderList("gone");
    await screen.findByText("gate.mp4");
    expect(screen.queryByText("processing")).not.toBeInTheDocument();
  });
});

describe("RecentAnalyses, deleting", () => {
  it("announces the result politely", async () => {
    analysesMock.mockResolvedValue([item()]);
    deleteMock.mockResolvedValue({
      analysis_id: "a1",
      deleted_files: 3,
      bytes_freed: 5 * 1024 * 1024,
      message: "Deleted.",
    } as Awaited<ReturnType<typeof api.delete>>);
    renderList();
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));

    const notice = await screen.findByText(/Deleted\./);
    expect(notice).toBeInTheDocument();
    expect(screen.getByText(/5\.0 MB freed/)).toBeInTheDocument();
    const status = screen.getAllByRole("status");
    expect(status[0]).toHaveAttribute("aria-live", "polite");
  });

  it("does nothing when the confirm is declined", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    analysesMock.mockResolvedValue([item()]);
    renderList();
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(deleteMock).not.toHaveBeenCalled();
  });

  it("asks before it deletes anything", async () => {
    analysesMock.mockResolvedValue([item()]);
    renderList();
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(window.confirm).toHaveBeenCalledWith(
      `Delete "gate.mp4" and all of its local files?`,
    );
  });

  it("announces a failed delete too", async () => {
    analysesMock.mockResolvedValue([item()]);
    deleteMock.mockRejectedValue(new ApiError("the file is in use", 409));
    renderList();
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    const title = await screen.findByText("The saved analyses could not be listed");
    const notice = title.closest("[role='status']");
    expect(notice).not.toBeNull();
    expect(within(notice as HTMLElement).getByText("the file is in use")).toBeInTheDocument();
  });
});

describe("RecentAnalyses, the bundled demo row", () => {
  const demo = item({ analysis_id: "demo", filename: "demo.mp4", source: "demo" });

  it("keeps Delete reachable and says out loud why it will not work", async () => {
    analysesMock.mockResolvedValue([demo]);
    renderList();
    const button = await screen.findByRole("button", { name: "Delete" });
    // aria-disabled, not disabled: a keyboard user can still land on it and
    // read why.  A `title` tooltip would be invisible to them.
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).not.toBeDisabled();

    expect(
      screen.getByText(/bundled demo dataset is read-only/),
    ).toBeInTheDocument();
  });

  it("really does nothing when that Delete is clicked", async () => {
    analysesMock.mockResolvedValue([demo]);
    renderList();
    const button = await screen.findByRole("button", { name: "Delete" });
    await userEvent.click(button);
    expect(deleteMock).not.toHaveBeenCalled();
    expect(window.confirm).not.toHaveBeenCalled();
  });

  it("is still reachable by keyboard", async () => {
    analysesMock.mockResolvedValue([demo]);
    renderList();
    const button = await screen.findByRole("button", { name: "Delete" });
    button.focus();
    expect(button).toHaveFocus();
  });

  it("leaves an ordinary row fully enabled", async () => {
    analysesMock.mockResolvedValue([item()]);
    renderList();
    const button = await screen.findByRole("button", { name: "Delete" });
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(button).not.toBeDisabled();
    await waitFor(() => expect(button).toBeEnabled());
  });
});
