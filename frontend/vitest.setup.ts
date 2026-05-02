import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import React from "react";
import { afterEach, beforeAll, vi } from "vitest";

import { MockEventSource } from "./tests/__helpers__/mock-event-source";

// jsdom does not ship `EventSource`. Install the mock so any hook under test
// receives the stub. Tests reset/open/close instances explicitly.
(globalThis as { EventSource: typeof EventSource }).EventSource =
  MockEventSource as unknown as typeof EventSource;

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = String(value);
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    get length() {
      return Object.keys(store).length;
    },
    key: (index: number) => Object.keys(store)[index] ?? null,
  };
})();

beforeAll(() => {
  Object.defineProperty(window, "localStorage", {
    value: localStorageMock,
    writable: true,
  });
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  MockEventSource.reset();
});

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => React.createElement("a", { href, ...props }, children),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));
