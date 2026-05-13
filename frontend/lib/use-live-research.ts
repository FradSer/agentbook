"use client";

import { useEffect, useRef, useState } from "react";

import { fetchLiveResearchSnapshot } from "@/lib/api";
import type { LiveResearchActive, LiveResearchSnapshot } from "@/lib/types";

export type LiveResearchStatus = "loading" | "open" | "fallback" | "error";

export type UseLiveResearchResult = {
  snapshot: LiveResearchSnapshot | null;
  status: LiveResearchStatus;
};

const STREAM_PATH = "/v1/dashboard/research/stream";
const FALLBACK_AFTER_ERRORS = 3;
const REST_POLL_MS = 10_000;
const REOPEN_PROBE_MS = 60_000;

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

/**
 * Subscribes to the live research SSE stream with REST snapshot fallback.
 *
 * Native `EventSource` ignores any `Last-Event-ID` we might want to send on
 * reconnect, so we never attach one — the server replays a fresh `snapshot`
 * frame on every connect, which is sufficient state.
 */
export function useLiveResearch(): UseLiveResearchResult {
  const [snapshot, setSnapshot] = useState<LiveResearchSnapshot | null>(null);
  const [status, setStatus] = useState<LiveResearchStatus>("loading");

  const esRef = useRef<EventSource | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const errorCountRef = useRef(0);
  const pollHandleRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reopenHandleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    const clearPoll = () => {
      if (pollHandleRef.current !== null) {
        clearInterval(pollHandleRef.current);
        pollHandleRef.current = null;
      }
    };
    const clearReopen = () => {
      if (reopenHandleRef.current !== null) {
        clearInterval(reopenHandleRef.current);
        reopenHandleRef.current = null;
      }
    };

    const closeStream = () => {
      esRef.current?.close();
      esRef.current = null;
    };

    const fetchOnce = async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const data = await fetchLiveResearchSnapshot(controller.signal);
        if (cancelled) return;
        setSnapshot(data);
      } catch {
        // Swallow — the next tick will retry.
      }
    };

    const enterFallback = () => {
      if (cancelled) return;
      closeStream();
      setStatus("fallback");
      void fetchOnce();
      if (pollHandleRef.current === null) {
        pollHandleRef.current = setInterval(() => {
          void fetchOnce();
        }, REST_POLL_MS);
      }
      if (reopenHandleRef.current === null) {
        reopenHandleRef.current = setInterval(() => {
          openStream();
        }, REOPEN_PROBE_MS);
      }
    };

    const openStream = () => {
      if (cancelled) return;
      closeStream();
      const url = `${API_BASE_URL}${STREAM_PATH}`;
      const es = new EventSource(url);
      esRef.current = es;
      errorCountRef.current = 0;

      es.addEventListener("snapshot", (evt) => {
        const data = JSON.parse(
          (evt as MessageEvent).data,
        ) as LiveResearchSnapshot | null;
        errorCountRef.current = 0;
        if (data) setSnapshot(data);
        setStatus("open");
        clearPoll();
        clearReopen();
      });

      es.addEventListener("research_started", (evt) => {
        const data = JSON.parse(
          (evt as MessageEvent).data,
        ) as LiveResearchActive;
        errorCountRef.current = 0;
        setSnapshot((prev) => {
          if (!prev) return prev;
          if (prev.active.some((a) => a.problem_id === data.problem_id)) {
            return prev;
          }
          return { ...prev, active: [data, ...prev.active] };
        });
      });

      es.addEventListener("research_ended", (evt) => {
        const data = JSON.parse((evt as MessageEvent).data) as {
          problem_id: string;
          last_cycle_at: string;
        };
        errorCountRef.current = 0;
        setSnapshot((prev) =>
          prev
            ? {
                ...prev,
                active: prev.active.filter(
                  (a) => a.problem_id !== data.problem_id,
                ),
                last_cycle_at: data.last_cycle_at,
              }
            : prev,
        );
      });

      es.addEventListener("error", () => {
        errorCountRef.current += 1;
        if (errorCountRef.current >= FALLBACK_AFTER_ERRORS) {
          enterFallback();
        }
      });
    };

    openStream();

    return () => {
      cancelled = true;
      closeStream();
      abortRef.current?.abort();
      abortRef.current = null;
      clearPoll();
      clearReopen();
    };
  }, []);

  return { snapshot, status };
}
