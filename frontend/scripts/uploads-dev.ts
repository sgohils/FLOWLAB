import { serve } from "@hono/node-server";
import app from "../api/blob-upload.ts";

const port = Number(process.env.PORT ?? 3001);
serve({ fetch: app.fetch, hostname: "127.0.0.1", port }, () => {
  console.log(`Upload service listening on http://127.0.0.1:${port}`);
});
