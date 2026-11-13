import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import SourcesPage from "@/app/(app)/sources/page";
import type { Job, JobStatus, Source } from "@/lib/api";

const SOURCE = { id: "s", type: "upload", name: "Uploads", config: {} };
const GITHUB = {
  id: "g",
  type: "github",
  name: "o/r",
  config: { repository: "o/r", branch: "main", include_paths: ["docs/**"] },
};

function job(status: JobStatus): Job {
  return {
    id: "job-1",
    source_id: "s",
    status,
    file_counts: { processed: 0, skipped: 0, failed: 0 },
    errors: [],
    created_at: "2026-11-07T10:00:00Z",
    started_at: null,
    finished_at: null,
  };
}

/** Serve the sources, then each jobs response in turn, repeating the last one. A new source
 * is x/y, and a sync answers syncReply. */
function serve(jobResponses: Job[][], sources: Source[] = [SOURCE], syncReply?: Response) {
  let jobCalls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/sources" && init?.method === "POST") {
        return Response.json({ ...GITHUB, id: "new", name: "x/y" }, { status: 201 });
      }
      if (url === "/api/sources") return Response.json(sources);
      if (url.endsWith("/sync")) return syncReply ?? Response.json({ job_id: "job-1" }, { status: 202 });
      const body = jobResponses[Math.min(jobCalls, jobResponses.length - 1)];
      jobCalls += 1;
      return Response.json(body);
    }),
  );
  return () => jobCalls;
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function advance(ms: number) {
  await act(() => vi.advanceTimersByTimeAsync(ms));
}

test("jobs are polled every 3 seconds while one is running, then polling stops", async () => {
  const jobCalls = serve([[job("running")], [job("running")], [job("succeeded")]]);
  render(<SourcesPage />);
  await advance(0);
  expect(jobCalls()).toBe(1);
  await advance(3000);
  expect(jobCalls()).toBe(2);
  await advance(3000);
  expect(jobCalls()).toBe(3);
  expect(screen.getByText("succeeded")).toBeInTheDocument();
  await advance(9000);
  expect(jobCalls()).toBe(3);
});

test("finished jobs are not polled", async () => {
  const jobCalls = serve([[job("partial")]]);
  render(<SourcesPage />);
  await advance(0);
  await advance(9000);
  expect(jobCalls()).toBe(1);
});

test("only GitHub sources have a Sync button", async () => {
  serve([[]], [SOURCE, GITHUB]);
  render(<SourcesPage />);
  await advance(0);
  const buttons = screen.getAllByRole("button", { name: /^sync/i });
  expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual(["Sync o/r"]);
});

test("syncing starts a job and polls it until it finishes", async () => {
  serve([[], [job("pending")], [job("succeeded")]], [SOURCE, GITHUB]);
  render(<SourcesPage />);
  await advance(0);
  fireEvent.click(screen.getByRole("button", { name: "Sync o/r" }));
  await advance(0);
  expect(fetch).toHaveBeenCalledWith("/api/sources/g/sync", expect.objectContaining({ method: "POST" }));
  expect(screen.getByText("pending")).toBeInTheDocument();
  await advance(3000);
  expect(screen.getByText("succeeded")).toBeInTheDocument();
});

test("a refused sync shows the reason", async () => {
  const refused = Response.json(
    { detail: { message: "This source already has an open job", job_id: "j0" } },
    { status: 409 },
  );
  serve([[]], [SOURCE, GITHUB], refused);
  render(<SourcesPage />);
  await advance(0);
  fireEvent.click(screen.getByRole("button", { name: "Sync o/r" }));
  await advance(0);
  expect(screen.getByRole("alert")).toHaveTextContent("This source already has an open job");
});

test("an added repository is listed with a Sync button", async () => {
  serve([[]]);
  render(<SourcesPage />);
  await advance(0);
  fireEvent.change(screen.getByLabelText(/^repository/i), { target: { value: "x/y" } });
  fireEvent.click(screen.getByRole("button", { name: /add repository/i }));
  await advance(0);
  expect(screen.getByRole("button", { name: "Sync x/y" })).toBeInTheDocument();
});

test("jobs name their source", async () => {
  serve([[{ ...job("succeeded"), source_id: "g" }]], [SOURCE, GITHUB]);
  render(<SourcesPage />);
  await advance(0);
  expect(screen.getAllByText("o/r").length).toBeGreaterThan(1);
});

test("a sync can defer embedding to the Kaggle notebook", async () => {
  serve([[]], [SOURCE, GITHUB]);
  render(<SourcesPage />);
  await advance(0);
  fireEvent.click(screen.getByLabelText(/embed syncs later/i));
  fireEvent.click(screen.getByRole("button", { name: "Sync o/r" }));
  await advance(0);
  expect(fetch).toHaveBeenCalledWith(
    "/api/sources/g/sync?defer_embedding=true",
    expect.objectContaining({ method: "POST" }),
  );
});
