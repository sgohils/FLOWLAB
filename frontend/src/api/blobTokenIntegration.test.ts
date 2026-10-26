// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { getPayloadFromClientToken } from "@vercel/blob/client";
import app from "../../api/blob-upload";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it("issues a scoped token through Hono and the real Blob SDK without uploading a file", async () => {
  const credential = "vercel_blob_rw_teststore_testsecret";
  vi.stubEnv("BACKEND_URL", "https://backend.internal/");
  vi.stubEnv("BLOB_READ_WRITE_TOKEN", credential);
  vi.stubEnv("VERCEL", "1");
  vi.stubEnv("VERCEL_ENV", "production");
  vi.stubEnv("VERCEL_PROJECT_PRODUCTION_URL", "flowlab.test");
  const proof = { analysis_id: "abc123abc123", token: "scoped-proof", pathname: "uploads/clip.mp4" };
  const authorize = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    expect(String(url)).toBe("https://backend.internal/api/uploads/authorize");
    expect(JSON.parse(String(init?.body))).toEqual(proof);
    return Response.json({ maximumSizeInBytes: 100, allowedContentTypes: ["video/mp4"] });
  });
  vi.stubGlobal("fetch", authorize);
  const response = await app.request("https://flowlab.test/api/blob-upload", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "blob.generate-client-token", payload: {
      pathname: proof.pathname, clientPayload: JSON.stringify(proof), multipart: true,
    } }),
  });
  expect(response.status).toBe(200);
  const body = await response.json();
  expect(body.type).toBe("blob.generate-client-token");
  expect(body.clientToken).toMatch(/^vercel_blob_client_/);
  expect(getPayloadFromClientToken(body.clientToken)).toMatchObject({
    pathname: proof.pathname,
    maximumSizeInBytes: 100,
    onUploadCompleted: {
      callbackUrl: "https://flowlab.test/api/blob-upload",
      tokenPayload: JSON.stringify(proof),
    },
  });
  expect(JSON.stringify(body)).not.toContain(credential);
  expect(authorize).toHaveBeenCalledTimes(1);
});

it("rejects unsigned completion callbacks before asking the backend to enqueue a job", async () => {
  vi.stubEnv("BACKEND_URL", "https://backend.internal/");
  vi.stubEnv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_teststore_testsecret");
  const backend = vi.fn();
  vi.stubGlobal("fetch", backend);
  const response = await app.request("https://flowlab.test/api/blob-upload", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "blob.upload-completed", payload: { blob: { pathname: "uploads/clip.mp4" } } }),
  });
  expect(response.status).toBe(400);
  expect((await response.json()).message).toContain("Missing callback signature");
  expect(backend).not.toHaveBeenCalled();
});
