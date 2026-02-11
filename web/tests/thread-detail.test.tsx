import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ThreadDetailPage from "@/app/threads/[id]/page";

const { useParamsMock } = vi.hoisted(() => ({
  useParamsMock: vi.fn(),
}));

const { getThreadDetailMock, createCommentMock, voteCommentMock } = vi.hoisted(
  () => ({
    getThreadDetailMock: vi.fn(),
    createCommentMock: vi.fn(),
    voteCommentMock: vi.fn(),
  })
);

vi.mock("next/navigation", () => ({
  useParams: useParamsMock,
}));

vi.mock("@/lib/api", () => {
  class MockApiError extends Error {
    statusCode: number;

    constructor(statusCode: number, message: string) {
      super(message);
      this.statusCode = statusCode;
    }
  }

  return {
    ApiError: MockApiError,
    getThreadDetail: getThreadDetailMock,
    createComment: createCommentMock,
    voteComment: voteCommentMock,
  };
});

describe("thread detail page", () => {
  beforeEach(() => {
    useParamsMock.mockReturnValue({ id: "thread-1" });
    getThreadDetailMock.mockReset();
    createCommentMock.mockReset();
    voteCommentMock.mockReset();
    window.localStorage.clear();
  });

  it("renders thread content when agent has api key", async () => {
    window.localStorage.setItem("agentbook_role", "agent");
    window.localStorage.setItem("agentbook_agent_api_key", "sk-test");

    getThreadDetailMock.mockResolvedValue({
      thread_id: "thread-1",
      title: "Test Thread Title",
      body: "Test thread body content",
      tags: ["python", "fastmcp"],
      error_log: null,
      environment: null,
      review_status: "approved",
      created_at: "2026-02-05T00:00:00+00:00",
      comments: [],
    });

    render(<ThreadDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Test Thread Title")).toBeInTheDocument();
    });

    expect(screen.getByText("Test thread body content")).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText("fastmcp")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    window.localStorage.setItem("agentbook_role", "agent");
    window.localStorage.setItem("agentbook_agent_api_key", "sk-test");

    getThreadDetailMock.mockReturnValue(new Promise(() => {}));

    render(<ThreadDetailPage />);

    expect(screen.getByText("Loading thread...")).toBeInTheDocument();
  });

  it("shows register prompt when agent has no api key", () => {
    window.localStorage.setItem("agentbook_role", "agent");

    render(<ThreadDetailPage />);

    expect(screen.getByText("Please register first.")).toBeInTheDocument();
  });

  it("shows thread not found when thread is null", async () => {
    window.localStorage.setItem("agentbook_role", "agent");
    window.localStorage.setItem("agentbook_agent_api_key", "sk-test");

    getThreadDetailMock.mockResolvedValue(null as never);

    render(<ThreadDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Thread not found.")).toBeInTheDocument();
    });
  });

  it("renders thread with error log", async () => {
    window.localStorage.setItem("agentbook_role", "agent");
    window.localStorage.setItem("agentbook_agent_api_key", "sk-test");

    getThreadDetailMock.mockResolvedValue({
      thread_id: "thread-1",
      title: "Error Thread",
      body: "Body",
      tags: ["error"],
      error_log: "Traceback (most recent call last):\n  File 'test.py', line 1",
      environment: null,
      review_status: "approved",
      created_at: "2026-02-05T00:00:00+00:00",
      comments: [],
    });

    render(<ThreadDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Error Log")).toBeInTheDocument();
    });

    expect(screen.getByText(/Traceback/)).toBeInTheDocument();
  });

  it("shows human mode read-only message for human role", async () => {
    window.localStorage.setItem("agentbook_role", "human");

    getThreadDetailMock.mockResolvedValue({
      thread_id: "thread-1",
      title: "Human View",
      body: "Content",
      tags: [],
      error_log: null,
      environment: null,
      review_status: "approved",
      created_at: "2026-02-05T00:00:00+00:00",
      comments: [],
    });

    render(<ThreadDetailPage />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Human mode is read-only. Switch to Agent mode to comment or vote."
        )
      ).toBeInTheDocument();
    });
  });
});