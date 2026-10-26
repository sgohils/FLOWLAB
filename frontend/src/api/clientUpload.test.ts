import { afterEach, expect, it, vi } from "vitest";
import { put } from "@vercel/blob/client";
import { api } from "./client";

vi.mock("@vercel/blob/client", () => ({ put: vi.fn(async () => ({})) }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("sends hosted video bytes directly to private Blob and finalizes with metadata only", async () => {
  const intent = { analysis_id: "abc123abc123", token: "secret", pathname: "uploads/clip.mp4" };
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(Response.json({ mode: "blob" }))
    .mockResolvedValueOnce(Response.json(intent))
    .mockResolvedValueOnce(Response.json({ clientToken: "vercel_blob_client_scoped" }))
    .mockResolvedValueOnce(Response.json({ analysis_id: intent.analysis_id }));
  vi.stubGlobal("fetch", fetchMock);
  const file = new File(["video bytes"], "clip.mp4", { type: "video/mp4" });
  const result = await api.upload(file);
  expect(result.analysis_id).toBe(intent.analysis_id);
  expect(put).toHaveBeenCalledWith(intent.pathname, file, expect.objectContaining({
    access: "private", token: "vercel_blob_client_scoped",
  }));
  expect(fetchMock.mock.calls[2]).toEqual(["/api/blob-upload", expect.objectContaining({
    body: JSON.stringify({ type: "blob.generate-client-token", payload: {
      pathname: intent.pathname, clientPayload: JSON.stringify(intent), multipart: true,
    } }),
  })]);
  expect(fetchMock).toHaveBeenLastCalledWith("/api/uploads/complete", expect.objectContaining({
    body: JSON.stringify(intent),
  }));
  expect(fetchMock.mock.calls.map(([url]) => url)).not.toContain("/api/uploads");
});

it("shows the upload handler's actionable error instead of the SDK's generic token failure", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(Response.json({ mode: "blob" }))
    .mockResolvedValueOnce(Response.json({ pathname: "uploads/clip.mp4" }))
    .mockResolvedValueOnce(Response.json({ message: "Missing backend binding", hint: "Redeploy services" }, { status: 503 })));
  await expect(api.upload(new File(["video"], "clip.mp4"))).rejects.toMatchObject({
    status: 503, message: "Missing backend binding", hint: "Redeploy services",
  });
  expect(put).not.toHaveBeenCalled();
});

it("identifies an upload endpoint swallowed by the SPA rewrite before sending video bytes", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(Response.json({ mode: "blob" }))
    .mockResolvedValueOnce(Response.json({ pathname: "uploads/clip.mp4" }))
    .mockResolvedValueOnce(new Response("<!doctype html><html>FLOWLAB</html>")));
  await expect(api.upload(new File(["video"], "clip.mp4"))).rejects.toMatchObject({
    status: 502, hint: expect.stringContaining("index.html"),
  });
  expect(put).not.toHaveBeenCalled();
});
