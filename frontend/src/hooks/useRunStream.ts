import { useEffect, useRef, useState } from "react";

export interface StreamEvent {
  type: string;
  payload: any;
  receivedAt: number;
}

export function useRunStream(runId: number | null) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (runId == null) return;
    setEvents([]);
    const es = new EventSource(`/api/runs/${runId}/events`);
    sourceRef.current = es;
    es.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        setEvents((prev) => [
          ...prev,
          { type: data.type, payload: data.payload, receivedAt: Date.now() },
        ]);
      } catch (err) {
        console.error("Bad SSE payload", err);
      }
    };
    es.onerror = () => {
      es.close();
    };
    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, [runId]);

  return events;
}
