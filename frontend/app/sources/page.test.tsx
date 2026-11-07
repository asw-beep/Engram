import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import SourcesPage from "@/app/sources/page";
import type { Job, JobStatus } from "@/lib/api";

const SOURCE = { id: "s", type: "upload", name: "Uploads", config: {} };

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

/** Serve the sources, then each jobs response in turn, repeating the last one. */
function serve(jobResponses: Job[][]) {
  let jobCalls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url === "/api/sources") return Response.json([SOURCE]);
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
