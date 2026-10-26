import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";
import { Hono } from "hono";

class UploadError extends Error {
  constructor(message: string, readonly status: number, readonly hint: string | null = null) {
    super(message);
  }
}

function failure(message: string, status: number, hint: string | null = null) {
  return Response.json({ error: message, message, hint }, { status });
}

export function GET(): Response {
  return Response.json({ message: "Use POST to authorize a video upload." }, {
    status: 405, headers: { Allow: "POST" },
  });
}

/** Vercel Node function: bindings resolve here at request time. */
export async function POST(request: Request): Promise<Response> {
  if (!process.env.BACKEND_URL) {
    return failure("The backend service binding is missing.", 503,
      "Redeploy the repository's services configuration so Vercel injects BACKEND_URL.");
  }
  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    return failure("The upload function has no Blob read-write token.", 503,
      "Connect the private Blob store to this project's Production environment and redeploy.");
  }
  const backend = async (path: string, payload: unknown) => {
    let response: Response;
    try {
      response = await fetch(new URL(path, `${process.env.BACKEND_URL!.replace(/\/+$/, "")}/`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch {
      throw new UploadError("The upload function could not reach the backend.", 503,
        "Check the backend service's runtime logs and retry.");
    }
    let body;
    try {
      body = await response.json();
    } catch {
      throw new UploadError("The upload backend returned an unexpected response.", 502,
        "Check the backend service binding and runtime logs.");
    }
    if (!response.ok) throw new UploadError(
      body.message ?? "Upload authorization failed.", response.status, body.hint ?? null,
    );
    return body;
  };
  try {
    const body = (await request.json()) as HandleUploadBody;
    const result = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname, clientPayload) => {
        const proof = JSON.parse(clientPayload ?? "{}");
        const limits = await backend("api/uploads/authorize", { ...proof, pathname });
        return {
          ...limits,
          addRandomSuffix: false,
          allowOverwrite: false,
          tokenPayload: JSON.stringify({ ...proof, pathname }),
        };
      },
      onUploadCompleted: async ({ blob, tokenPayload }) => {
        const proof = JSON.parse(tokenPayload ?? "{}");
        await backend("api/uploads/complete", { ...proof, pathname: blob.pathname });
      },
    });
    return Response.json(result);
  } catch (error) {
    return failure(
      error instanceof Error ? error.message : "The upload failed.",
      error instanceof UploadError ? error.status : 400,
      error instanceof UploadError ? error.hint : null,
    );
  }
}

// A services-mode Vite build emits static assets. This entry point belongs to
// the dedicated Node upload service so token requests always reach a function.
const app = new Hono();
app.post("/api/blob-upload", (context) => POST(context.req.raw));
app.get("/api/blob-upload", () => GET());
export default app;
