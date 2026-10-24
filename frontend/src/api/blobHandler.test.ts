import { afterEach, expect, it, vi } from "vitest";
import { handleUpload } from "@vercel/blob/client";
import { POST } from "../../api/blob-upload";

vi.mock("@vercel/blob/client", () => ({ handleUpload: vi.fn() }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.clearAllMocks();
});

it("fails clearly when Vercel has not injected the backend binding", async () => {
  vi.stubEnv("BACKEND_URL", "");
  const response = await POST(new Request("https://app.test/api/blob-upload", { method: "POST" }));
  expect(response.status).toBe(503);
  expect(handleUpload).not.toHaveBeenCalled();
});

it("uses the runtime binding to authorize and finalize a scoped upload", async () => {
  vi.stubEnv("BACKEND_URL", "https://backend.internal/");
  const fetchMock = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) =>
    Response.json({ maximumSizeInBytes: 123 }));
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(handleUpload).mockImplementation(async (options) => {
    const proof = { analysis_id: "abc123abc123", token: "secret" };
    const token = await options.onBeforeGenerateToken("uploads/clip.mp4", JSON.stringify(proof), true);
    expect(token.allowOverwrite).toBe(false);
    expect(token.maximumSizeInBytes).toBe(123);
    if (!options.onUploadCompleted) throw new Error("Missing completion handler");
    await options.onUploadCompleted({
      blob: { pathname: "uploads/clip.mp4" } as Parameters<
        NonNullable<typeof options.onUploadCompleted>
      >[0]["blob"],
      tokenPayload: token.tokenPayload,
    });
    return { type: "blob.upload-completed", response: "ok" };
  });
  const response = await POST(new Request("https://app.test/api/blob-upload", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
  }));
  expect(response.status).toBe(200);
  expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
    "https://backend.internal/api/uploads/authorize",
    "https://backend.internal/api/uploads/complete",
  ]);
});
