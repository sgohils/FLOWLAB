import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { AnalysisListItem } from "../types";
import {
  formatBytes,
  formatNumber,
  formatTimecode,
  formatWithUnit,
} from "../utils/format";
import { Button, Notice, Panel, Row } from "./Primitives";

/** Matches the page size `api.analyses()` asks for. */
const LIST_LIMIT = 100;

/**
 * The analyses already on this machine, served by GET /api/analyses.
 *
 * One page of the 100 the endpoint will serve at most - so the wording on this
 * list says "the most recent", never "everything".
 *
 * Nothing is deleted implicitly: removing a row here deletes the record *and*
 * its local files, so it asks first and then reports what was actually freed.
 * The bundled demo dataset is read-only, so it is shown but never deletable.
 */
export function RecentAnalyses({ currentId }: { currentId: string | null }) {
  const navigate = useNavigate();
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.analyses(LIST_LIMIT));
    } catch (caught) {
      setItems([]);
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The list of past analyses could not be read.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const remove = async (item: AnalysisListItem) => {
    if (!window.confirm(`Delete "${item.filename}" and all of its local files?`)) return;
    setBusyId(item.analysis_id);
    setError(null);
    setNotice(null);
    try {
      const result = await api.delete(item.analysis_id);
      setNotice(
        `${result.message} ${formatNumber(result.deleted_files, 0)} file(s), ${formatBytes(
          result.bytes_freed,
        )} freed.`,
      );
      await refresh();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "That analysis could not be deleted.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const open = (item: AnalysisListItem) => {
    navigate(`/analysis/${item.analysis_id}`);
  };

  return (
    <div className="space-y-3">
      {error && (
        <Notice tone="error" title="The saved analyses could not be listed" live>
          {error}
        </Notice>
      )}
      {notice && (
        <Notice tone="success" live>
          {notice}
        </Notice>
      )}

      {loading && items.length === 0 ? (
        <Panel role="status" className="p-5 text-[13px] text-ink-faint">
          Loading saved analyses…
        </Panel>
      ) : items.length === 0 ? (
        <Panel className="p-5 text-[13px] leading-relaxed text-ink-soft">
          Nothing stored on this machine yet. Analyses you upload, and the demo
          dataset, are listed here so you can reopen or delete them.
        </Panel>
      ) : (
        <Panel>
          <ul className="divide-y divide-rule-soft">
            {items.map((item) => {
              const current = item.analysis_id === currentId;
              const running = item.status === "queued" || item.status === "processing";
              const demo = item.source === "demo";
              return (
                <li
                  key={item.analysis_id}
                  className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5"
                >
                  <div className="min-w-[200px] flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="text-[13px] font-medium text-ink">
                        {item.filename}
                      </span>
                      {demo && (
                        <span className="rounded border border-caution/40 bg-caution-soft px-1.5 py-0.5 text-[9px] uppercase tracking-[0.12em] text-caution">
                          demo
                        </span>
                      )}
                      {current && (
                        <span className="rounded border border-rule px-1.5 py-0.5 text-[9px] uppercase tracking-[0.12em] text-ink-faint">
                          open
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-[11px] text-ink-faint">
                      {item.analysis_id} · analysed{" "}
                      {formatWhen(item.created_at)}
                    </p>
                  </div>

                  <dl className="grid w-full grid-cols-2 gap-x-6 gap-y-1 text-[12px] sm:w-auto sm:grid-cols-4">
                    <Row label="Duration" value={formatTimecode(item.duration)} />
                    <Row label="Vehicles" value={formatNumber(item.vehicles_tracked, 0)} />
                    <Row
                      label="Peak queue"
                      value={
                        running
                          ? "processing"
                          : formatWithUnit(item.peak_queue, "vehicles", 0)
                      }
                    />
                    <Row
                      label="Throughput"
                      value={
                        running
                          ? "processing"
                          : formatWithUnit(item.throughput_per_minute, "veh/min")
                      }
                    />
                  </dl>

                  <div className="flex flex-col items-end gap-1">
                    <div className="flex items-center gap-2">
                      <Button variant="secondary" onClick={() => open(item)}>
                        {running ? "Watch" : "Reopen"}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          // aria-disabled only announces; the guard is here.
                          if (!demo) void remove(item);
                        }}
                        disabled={busyId === item.analysis_id}
                        ariaDisabled={demo}
                        title={demo ? undefined : "Delete the record and its local files."}
                      >
                        Delete
                      </Button>
                    </div>
                    {demo && (
                      <span className="max-w-[17rem] text-right text-[10px] leading-snug text-ink-faint">
                        The bundled demo dataset is read-only, so there is nothing here to
                        delete.
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </Panel>
      )}

      <p className="text-[11px] leading-relaxed text-ink-faint">
        These are the {LIST_LIMIT} most recent analyses in the local database. Opening
        one loads its stored measurements; deleting one also removes the uploaded video,
        the annotated copy and the results.
      </p>
    </div>
  );
}

/** A short, local date/time for the list; never anything about the footage. */
function formatWhen(timestamp: number): string {
  if (!Number.isFinite(timestamp) || timestamp <= 0) return "unknown date";
  return new Date(timestamp * 1000).toLocaleString();
}
