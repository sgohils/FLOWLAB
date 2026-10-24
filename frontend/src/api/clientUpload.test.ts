import { afterEach, expect, it, vi } from "vitest";
import { upload } from "@vercel/blob/client";
import { api } from "./client";

vi.mock("@vercel/blob/client", () => ({ upload: vi.fn(async () => ({})) }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("sends hosted video bytes directly to private Blob and finalizes with metadata only", async () => {
  const intent = { analysis_id: "abc123abc123", token: "secret", pathname: "uploads/clip.mp4" };
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(Response.json({ mode: "blob" }))
    .mockResolvedValueOnce(Response.json(intent))
    .mockResolvedValueOnce(Response.json({ analysis_id: intent.analysis_id }));
  vi.stubGlobal("fetch", fetchMock);
  const file = new File(["video bytes"], "clip.mp4", { type: "video/mp4" });
  const result = await api.upload(file);
  expect(result.analysis_id).toBe(intent.analysis_id);
  expect(upload).toHaveBeenCalledWith(intent.pathname, file, expect.objectContaining({
    access: "private", handleUploadUrl: "/api/blob-upload", clientPayload: JSON.stringify(intent),
  }));
  expect(fetchMock).toHaveBeenLastCalledWith("/api/uploads/complete", expect.objectContaining({
    body: JSON.stringify(intent),
  }));
  expect(fetchMock.mock.calls.map(([url]) => url)).not.toContain("/api/uploads");
});
