import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Health } from "../types";
import { Notice } from "./Primitives";

/**
 * Reads GET /api/health and says so *before* an upload if something is wrong.
 * Without this, a user waits for an upload to fail and has no way to tell a
 * missing model file from bad footage.
 *
 * Only a problem is rendered, plus a quiet line while the first answer is on
 * its way: on a cold backend the request takes seconds, and silence there reads
 * as a broken page rather than as a starting server.
 *
 * A failed request is retried a bounded number of times, because the commonest
 * cause of a first refusal is a backend that is still booting rather than one
 * that is down.  After the last attempt the notice stops, so a genuinely
 * unreachable backend does not keep a page full of timers alive.
 *
 * The result is announced politely so a screen reader hears the failure.
 */

/** Total attempts, including the first. */
const ATTEMPTS = 3;

/** Wait before each retry, in milliseconds. */
const RETRY_DELAYS_MS = [1200, 3000];

export function ApiHealthBanner() {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);
  /** Which attempt is in flight, or 0 once the attempts are exhausted. */
  const [attempt, setAttempt] = useState(1);

  useEffect(() => {
    let cancelled = false;
    const timers: number[] = [];

    const ask = async (index: number) => {
      setAttempt(index + 1);
      try {
        const result = await api.health();
        if (cancelled) return;
        setHealth(result);
        setFailed(false);
      } catch {
        if (cancelled) return;
        setFailed(true);
        const delay = RETRY_DELAYS_MS[index];
        if (delay === undefined) {
          setAttempt(0);
          return;
        }
        timers.push(window.setTimeout(() => void ask(index + 1), delay));
      }
    };

    void ask(0);
    return () => {
      cancelled = true;
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, []);

  if (failed) {
    return (
      <div className="mb-6">
        <Notice tone="caution" title="The backend is not answering" live>
          <p>
            FLOWLAB could not read <code className="font-mono">/api/health</code>. Until
            it answers, nothing can be uploaded or analysed.
          </p>
          {attempt > 0 ? (
            <p className="mt-1">
              Still retrying - attempt {attempt} of {ATTEMPTS}. A backend that is only
              just starting answers on its own; nothing needs reloading.
            </p>
          ) : (
            <p className="mt-1">
              Tried {ATTEMPTS} times over about 4 seconds. Start the backend and reload
              this page.
            </p>
          )}
        </Notice>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="mb-6" role="status" aria-live="polite">
        <p className="text-[11px] text-ink-faint">Checking the backend…</p>
      </div>
    );
  }

  // Branch on `status`, not only on `model_loaded`: a degraded backend can hold a
  // loaded model and still be reporting something the user needs to know, and
  // its `message` is the only place that says what.
  if (health.status === "ok" && health.model_loaded) return null;

  if (health.model_loaded) {
    return (
      <div className="mb-6">
        <Notice tone="caution" title="The backend is running degraded" live>
          <p>
            The API is up and {health.model_name} is loaded on {health.device}, so an
            upload would be detected normally, but it is reporting a problem.
          </p>
          {health.message && (
            <p className="mt-1 font-mono text-[12px] opacity-85">{health.message}</p>
          )}
        </Notice>
      </div>
    );
  }

  return (
    <div className="mb-6">
      <Notice tone="caution" title="The detection model is not loaded" live>
        <p>
          The API is running on {health.device} but {health.model_name} could not be
          loaded, so an upload would fail during detection. The bundled demo dataset
          still works, because it is measured from stored trajectories.
        </p>
        {health.message && (
          <p className="mt-1 font-mono text-[12px] opacity-85">{health.message}</p>
        )}
      </Notice>
    </div>
  );
}
