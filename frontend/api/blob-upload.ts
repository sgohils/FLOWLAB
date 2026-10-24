import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";

/** Vercel Node function: bindings resolve here at request time. */
export async function POST(request: Request): Promise<Response> {
  if (!process.env.BACKEND_URL) {
    return Response.json({ message: "The backend service binding is missing." }, { status: 503 });
  }
  const backend = async (path: string, payload: unknown) => {
    const response = await fetch(new URL(path, process.env.BACKEND_URL), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.message ?? "Upload authorization failed.");
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
    return Response.json(
      { message: error instanceof Error ? error.message : "The upload failed." },
      { status: 400 },
    );
  }
}
