import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import JobList from "@/components/JobList";
import type { Job, JobStatus } from "@/lib/api";

function job(fields: Partial<Omit<Job, "status">> & { status?: string }): Job {
  return {
    id: "job-1",
    source_id: "s",
    file_counts: { processed: 2, skipped: 1, failed: 0 },
    errors: [],
    created_at: "2026-11-07T10:00:00Z",
    started_at: "2026-11-07T10:00:01Z",
    finished_at: null,
    ...fields,
    status: (fields.status ?? "succeeded") as JobStatus,
  };
}

test("shows status, counts and file errors", () => {
  render(
    <JobList
      jobs={[job({ status: "partial", errors: [{ path: "bad.md", reason: "no text" }] })]}
      onRetry={vi.fn()}
    />,
  );
  expect(screen.getByText("partial")).toBeInTheDocument();
  expect(screen.getByText(/bad\.md.*no text/)).toBeInTheDocument();
});

test.each(["partial", "failed", "interrupted"])("%s can be retried", (status) => {
  const onRetry = vi.fn();
  render(<JobList jobs={[job({ id: "1", status })]} onRetry={onRetry} />);
  fireEvent.click(screen.getByRole("button", { name: /retry/i }));
  expect(onRetry).toHaveBeenCalledWith("1");
});

test.each(["running", "succeeded", "awaiting_embedding"])("%s cannot be retried", (status) => {
  render(<JobList jobs={[job({ status })]} onRetry={vi.fn()} />);
  expect(screen.queryByRole("button", { name: /retry/i })).toBeNull();
});

test("names each job's source when its name is known", () => {
  render(
    <JobList
      jobs={[job({ id: "a", source_id: "g" }), job({ id: "b", source_id: "gone" })]}
      sourceNames={{ g: "kubernetes/website" }}
      onRetry={vi.fn()}
    />,
  );
  expect(screen.getAllByText("kubernetes/website")).toHaveLength(1);
});
