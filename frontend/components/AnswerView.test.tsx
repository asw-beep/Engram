import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import AnswerView from "@/components/AnswerView";
import type { Citation, Outcome, QuestionResponse } from "@/lib/api";

function citation(marker: number, path = "docs/guide.md"): Citation {
  return {
    marker,
    document_path: path,
    source_name: "Uploads",
    heading_path: ["Guide"],
    start_line: 1,
    end_line: 4,
    page_start: null,
    page_end: null,
    revision: null,
    snippet: "A short excerpt.",
    url: null,
  };
}

function response(fields: Partial<QuestionResponse>): QuestionResponse {
  return { id: "q1", outcome: "answered", answer: null, citations: [], passages: [], ...fields };
}

const answered = (answer: string, citations: Citation[]) => response({ answer, citations });
const noAnswer = (outcome: Outcome) => response({ outcome });
const quota = (passages: Citation[]) => response({ outcome: "quota_exhausted", passages });

test("markers become buttons that reveal the source", async () => {
  render(<AnswerView response={answered("Pods run [1].", [citation(1, "concepts/pods.md")])} />);
  expect(screen.queryByText("concepts/pods.md")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "[1]" }));
  expect(screen.getByText("concepts/pods.md")).toBeInTheDocument();
});

test("model output stays plain text", () => {
  const { container } = render(
    <AnswerView response={answered("<img src=x onerror=alert(1)> [1]", [citation(1)])} />,
  );
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
});

test("citation link comes only from the backend url", () => {
  render(<AnswerView response={answered("See [docs](http://evil.test) [1]", [citation(1)])} />);
  expect(screen.queryByRole("link", { name: "docs" })).toBeNull();
});

test("a marker without a citation stays as text", () => {
  render(<AnswerView response={answered("Odd [7].", [])} />);
  expect(screen.queryByRole("button", { name: "[7]" })).toBeNull();
});

test.each([
  ["insufficient_evidence", /not enough evidence/i],
  ["unverifiable", /couldn't produce a verifiable answer/i],
  ["llm_error", /answers are unavailable/i],
] as const)("%s shows its message", (outcome, message) => {
  render(<AnswerView response={noAnswer(outcome)} />);
  expect(screen.getByText(message)).toBeInTheDocument();
});

test("quota_exhausted shows passages and a note", () => {
  render(<AnswerView response={quota([citation(1, "a.md")])} />);
  expect(screen.getByText(/ai answers are unavailable until the limit resets/i)).toBeInTheDocument();
  expect(screen.getByText("a.md")).toBeInTheDocument();
});

test("code indexing next to a word stays text", () => {
  render(<AnswerView response={answered("Use items[1] here [1].", [citation(1)])} />);
  expect(screen.getAllByRole("button", { name: "[1]" })).toHaveLength(1);
  expect(screen.getByText(/Use items\[1\] here/)).toBeInTheDocument();
});

test("a source shows its headings, range, revision and snippet", async () => {
  const source = { ...citation(1), heading_path: ["Guide", "Install"], revision: "abc1234def5678" };
  render(<AnswerView response={answered("Yes [1].", [source])} />);
  await userEvent.click(screen.getByRole("button", { name: "[1]" }));
  expect(screen.getByText("Guide › Install")).toBeInTheDocument();
  expect(screen.getByText("Uploads, lines 1–4, revision abc1234def56")).toBeInTheDocument();
  expect(screen.getByText("A short excerpt.")).toBeInTheDocument();
});

test.each([
  ["https://github.com/o/r/blob/abc/a.md#L1-L4", true],
  ["javascript:alert(1)", false],
  [null, false],
])("source url %s gives a link: %s", async (url, linked) => {
  render(<AnswerView response={answered("Yes [1].", [{ ...citation(1), url }])} />);
  await userEvent.click(screen.getByRole("button", { name: "[1]" }));
  const link = screen.queryByRole("link", { name: "Open in the repository" });
  expect(link !== null).toBe(linked);
  if (url && linked) expect(link).toHaveAttribute("href", url);
});
