import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

/**
 * The client owns the query strings, so the shape of a request is asserted
 * here rather than through whichever component happens to make it.
 */
function stubFetch(body: unknown = []) {
  const fetchMock = vi.fn(
    async (_url: string, _init?: RequestInit) =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api.analyses", () => {
  it("asks for the largest page the endpoint serves, not the 25-row default", async () => {
    // routes_analysis.py: Query(default=25, ge=1, le=100).  Without the
    // explicit limit the oldest analyses vanish under the interface's claim
    // to show everything.
    const fetchMock = stubFetch();
    await api.analyses();
    expect(fetchMock).toHaveBeenCalledWith("/api/analyses?limit=100", undefined);
  });

  it("honours an explicit page size", async () => {
    const fetchMock = stubFetch();
    await api.analyses(10);
    expect(fetchMock).toHaveBeenCalledWith("/api/analyses?limit=10", undefined);
  });

  it("defaults to exactly the endpoint maximum, not one past it", async () => {
    // le=100: 101 would come back as a 422, not as a longer page.
    const fetchMock = stubFetch();
    await api.analyses();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/analyses?limit=100");
  });
});

describe("api.health", () => {
  it("reads the health endpoint", async () => {
    const fetchMock = stubFetch({
      status: "ok",
      model_loaded: true,
      device: "cpu",
      model_name: "yolov8n.pt",
      message: null,
    });
    const result = await api.health();
    expect(fetchMock).toHaveBeenCalledWith("/api/health", undefined);
    expect(result.status).toBe("ok");
  });
});
