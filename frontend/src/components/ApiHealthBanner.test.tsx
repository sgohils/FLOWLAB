import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiHealthBanner } from "./ApiHealthBanner";
import { api } from "../api/client";
import type { Health } from "../types";

vi.mock("../api/client", () => ({ api: { health: vi.fn() } }));

const healthMock = vi.mocked(api.health);

function health(overrides: Partial<Health> = {}): Health {
  return {
    status: "ok",
    model_loaded: true,
    device: "cpu",
    model_name: "yolov8n.pt",
    message: null,
    ...overrides,
  };
}

beforeEach(() => {
  healthMock.mockReset();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
});

/** Lets every already-resolved promise settle inside act(). */
async function flush() {
  await vi.waitFor(() => {}, { timeout: 0 });
}

describe("ApiHealthBanner", () => {
  it("does not report a missing model when hosted detection belongs to a queue worker", async () => {
    healthMock.mockResolvedValue(health({ model_loaded: false, processing_mode: "queue" }));
    const { container } = render(<ApiHealthBanner />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
  it("shows nothing at all when the backend is healthy", async () => {
    healthMock.mockResolvedValue(health());
    const { container } = render(<ApiHealthBanner />);
    await flush();
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("says it is checking while the answer is on its way", async () => {
    // A cold backend takes seconds; silence there reads as a broken page.
    healthMock.mockReturnValue(new Promise(() => {}));
    render(<ApiHealthBanner />);
    expect(screen.getByRole("status")).toHaveTextContent("Checking the backend");
    expect(healthMock).toHaveBeenCalledTimes(1);
  });

  it("stops saying it is checking once the answer arrives", async () => {
    healthMock.mockResolvedValue(health());
    render(<ApiHealthBanner />);
    await flush();
    await waitFor(() =>
      expect(screen.queryByText(/Checking the backend/)).not.toBeInTheDocument(),
    );
  });

  it("names the model and the device when the model is not loaded", async () => {
    healthMock.mockResolvedValue(
      health({ status: "degraded", model_loaded: false, device: "cpu", model_name: "yolov8n.pt" }),
    );
    render(<ApiHealthBanner />);
    await flush();
    const notice = await screen.findByText("The detection model is not loaded");
    expect(notice).toBeInTheDocument();
    expect(screen.getByText(/yolov8n\.pt/)).toBeInTheDocument();
    expect(screen.getByText(/cpu/)).toBeInTheDocument();
  });

  it("shows the backend's message under a model that failed to load", async () => {
    healthMock.mockResolvedValue(
      health({ status: "degraded", model_loaded: false, message: "FileNotFoundError: yolov8n.pt" }),
    );
    render(<ApiHealthBanner />);
    await flush();
    expect(await screen.findByText("FileNotFoundError: yolov8n.pt")).toBeInTheDocument();
  });

  it("reports a degraded backend that still has its model, instead of nothing", async () => {
    // status degraded + model_loaded true used to render an empty banner: the
    // message was fetched over the wire and then dropped.
    healthMock.mockResolvedValue(
      health({ status: "degraded", model_loaded: true, message: "GPU out of memory" }),
    );
    render(<ApiHealthBanner />);
    await flush();
    expect(await screen.findByText("The backend is running degraded")).toBeInTheDocument();
    expect(screen.getByText("GPU out of memory")).toBeInTheDocument();
  });

  it("still says something useful about a degraded backend with no message", async () => {
    healthMock.mockResolvedValue(health({ status: "degraded", message: null }));
    render(<ApiHealthBanner />);
    await flush();
    await screen.findByText("The backend is running degraded");
    expect(screen.queryByText("GPU out of memory")).not.toBeInTheDocument();
  });

  it("announces every notice politely, so a screen reader hears it", async () => {
    healthMock.mockResolvedValue(health({ status: "degraded", model_loaded: false }));
    render(<ApiHealthBanner />);
    await flush();
    await screen.findByText("The detection model is not loaded");
    const status = screen.getAllByRole("status");
    expect(status.length).toBeGreaterThan(0);
    expect(status[0]).toHaveAttribute("aria-live", "polite");
  });
});

describe("ApiHealthBanner, an unreachable backend", () => {
  it("says so instead of rendering nothing", async () => {
    healthMock.mockRejectedValue(new Error("offline"));
    render(<ApiHealthBanner />);
    await flush();
    expect(await screen.findByText("The backend is not answering")).toBeInTheDocument();
  });

  it("recovers by itself when a late backend answers, with no reload", async () => {
    healthMock
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(health());
    render(<ApiHealthBanner />);
    await flush();
    await screen.findByText("The backend is not answering");

    // First retry is scheduled at 1200 ms; nothing else advances the clock.
    await vi.advanceTimersByTimeAsync(1500);
    await waitFor(() => expect(healthMock).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.queryByText("The backend is not answering")).not.toBeInTheDocument(),
    );
  });

  it("says it is still retrying while a retry is outstanding", async () => {
    healthMock.mockRejectedValue(new Error("offline"));
    render(<ApiHealthBanner />);
    await flush();
    await screen.findByText("The backend is not answering");
    await vi.advanceTimersByTimeAsync(1500);
    expect(await screen.findByText(/Still retrying/)).toBeInTheDocument();
  });

  it("stops after a bounded number of attempts rather than looping forever", async () => {
    healthMock.mockRejectedValue(new Error("offline"));
    render(<ApiHealthBanner />);
    await flush();
    await screen.findByText("The backend is not answering");

    await vi.advanceTimersByTimeAsync(10_000);
    await waitFor(() => expect(healthMock).toHaveBeenCalledTimes(3));

    // No further timers: a genuinely down backend must not keep retrying.
    await vi.advanceTimersByTimeAsync(60_000);
    expect(healthMock).toHaveBeenCalledTimes(3);
    expect(screen.queryByText(/Still retrying/)).not.toBeInTheDocument();
    expect(screen.getByText(/Tried 3 times/)).toBeInTheDocument();
  });

  it("asks for the backend once more after each retry and settles on the notice", async () => {
    healthMock.mockRejectedValueOnce(new Error("offline"));
    healthMock.mockRejectedValueOnce(new Error("offline"));
    healthMock.mockResolvedValueOnce(health());
    render(<ApiHealthBanner />);
    await flush();
    await vi.advanceTimersByTimeAsync(10_000);
    await waitFor(() => expect(healthMock).toHaveBeenCalledTimes(3));
    await waitFor(() =>
      expect(screen.queryByText(/Still retrying|Tried 3 times/)).not.toBeInTheDocument(),
    );
  });
});
