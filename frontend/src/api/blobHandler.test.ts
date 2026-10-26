import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { handleUpload } from "@vercel/blob/client";
import app, { GET, POST } from "../../api/blob-upload";
import config from "../../../vercel.json";

vi.mock("@vercel/blob/client", () => ({ handleUpload: vi.fn() }));

beforeEach(() => { vi.stubEnv("BLOB_READ_WRITE_TOKEN", "test-credential"); });

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

it("keeps API paths out of the SPA fallback while supporting page deep links", () => {
  const spaRoutes = config.services.frontend.rewrites.map(({ source }) => new RegExp(`^${source}$`));
  for (const path of ["/api/blob-upload", "/api/blob-upload/", "/api"]) {
    expect(spaRoutes.some((route) => route.test(path)), path).toBe(false);
  }
  for (const path of ["/", "/analysis/demo", "/simulation/demo", "/brief/demo"]) {
    expect(spaRoutes.some((route) => route.test(path)), path).toBe(true);
  }
  const target = config.rewrites.find(({ source }) => new RegExp(`^${source}$`).test("/api/blob-upload"));
  expect(target?.destination.service).toBe("uploads");
  expect(config.services.uploads.bindings[0]).toMatchObject({ service: "backend", env: "BACKEND_URL" });
});

it("serves token requests through the dedicated Node service entry point", async () => {
  vi.stubEnv("BACKEND_URL", "");
  const response = await app.request("http://uploads.test/api/blob-upload", { method: "POST", body: "{}" });
  expect(response.status).toBe(503);
  expect((await response.json()).message).toContain("binding is missing");
});

it("answers GET with JSON rather than the website HTML", async () => {
  const response = GET();
  expect(response.status).toBe(405);
  expect(response.headers.get("Allow")).toBe("POST");
  expect(response.headers.get("Content-Type")).toContain("application/json");
});

it("identifies a missing token in the Node function separately from the backend configuration", async () => {
  vi.stubEnv("BACKEND_URL", "https://backend.internal/");
  vi.stubEnv("BLOB_READ_WRITE_TOKEN", "");
  const response = await POST(new Request("https://app.test/api/blob-upload", { method: "POST" }));
  expect(response.status).toBe(503);
  expect((await response.json()).message).toContain("no Blob read-write token");
  expect(handleUpload).not.toHaveBeenCalled();
});

it("preserves the backend's status and database setup hint", async () => {
  vi.stubEnv("BACKEND_URL", "https://backend.internal/service");
  const fetchMock = vi.fn().mockResolvedValue(Response.json({
    message: "Database not initialized", hint: "Run the migration",
  }, { status: 503 }));
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(handleUpload).mockImplementation(async (options) => {
    await options.onBeforeGenerateToken("uploads/clip.mp4", "{}", true);
    return { type: "blob.upload-completed", response: "ok" };
  });
  const response = await POST(new Request("https://app.test/api/blob-upload", { method: "POST", body: "{}" }));
  expect(response.status).toBe(503);
  expect(await response.json()).toMatchObject({ message: "Database not initialized", hint: "Run the migration" });
  expect(String(fetchMock.mock.calls[0][0])).toBe("https://backend.internal/service/api/uploads/authorize");
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
