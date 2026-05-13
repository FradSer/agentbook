/**
 * Minimal `EventSource` stub for jsdom (which does not ship `EventSource`).
 * Tests can:
 *   - inspect `MockEventSource.instances` to assert on subscriptions and lifecycle
 *   - call `dispatch(event, data)` to emit fake SSE messages
 *   - call `emitError()` to simulate a connection failure
 */

type Listener = (evt: MessageEvent | Event) => void;

export class MockEventSource {
  static instances: MockEventSource[] = [];

  static reset(): void {
    MockEventSource.instances = [];
  }

  /** Open instances only (skip closed). */
  static get open(): MockEventSource[] {
    return MockEventSource.instances.filter((i) => !i.closed);
  }

  url: string;
  withCredentials: boolean;
  readyState = 0;
  closed = false;
  listeners: Record<string, Listener[]> = {};
  // `EventSource` exposes `onerror`/`onmessage` properties; the hook uses
  // `addEventListener` exclusively, but we still allow direct assignment.
  onerror: ((evt: Event) => void) | null = null;
  onmessage: ((evt: MessageEvent) => void) | null = null;
  onopen: ((evt: Event) => void) | null = null;

  constructor(url: string, init?: { withCredentials?: boolean }) {
    this.url = url;
    this.withCredentials = init?.withCredentials ?? false;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, handler: Listener): void {
    const bucket = this.listeners[event] ?? [];
    bucket.push(handler);
    this.listeners[event] = bucket;
  }

  removeEventListener(event: string, handler: Listener): void {
    this.listeners[event] = (this.listeners[event] ?? []).filter(
      (h) => h !== handler,
    );
  }

  close(): void {
    this.closed = true;
    this.readyState = 2;
  }

  /** Test-only: dispatch a fake SSE event of `event` carrying `data`. */
  dispatch(event: string, data: unknown): void {
    if (this.closed) return;
    const payload =
      typeof data === "string" ? data : JSON.stringify(data ?? null);
    const evt = new MessageEvent(event, { data: payload });
    for (const handler of this.listeners[event] ?? []) {
      handler(evt);
    }
    if (event === "message" && this.onmessage) this.onmessage(evt);
  }

  /** Test-only: simulate a connection error. */
  emitError(): void {
    if (this.closed) return;
    const evt = new Event("error");
    for (const handler of this.listeners.error ?? []) {
      handler(evt);
    }
    if (this.onerror) this.onerror(evt);
  }
}
