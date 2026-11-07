import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

import AskForm from "@/components/AskForm";

afterEach(() => {
  vi.unstubAllGlobals();
});

function respond(status: number, body: string, contentType = "application/json") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body, { status, headers: { "Content-Type": contentType } })),
  );
}

async function ask(question = "how do pods work") {
  render(<AskForm />);
  await userEvent.type(screen.getByRole("textbox", { name: "Question" }), question);
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
}

test("an answer is shown when the API responds", async () => {
  respond(
    200,
    JSON.stringify({ id: "q1", outcome: "insufficient_evidence", answer: null, citations: [], passages: [] }),
  );
  await ask();
  expect(await screen.findByText(/not enough evidence/i)).toBeInTheDocument();
});

test("the question is sent trimmed", async () => {
  respond(200, JSON.stringify({ id: "q1", outcome: "llm_error", answer: null, citations: [], passages: [] }));
  await ask("  how do pods work  ");
  await screen.findByText(/answers are unavailable/i);
  const [, init] = vi.mocked(fetch).mock.calls[0];
  expect(JSON.parse(init?.body as string)).toEqual({ question: "how do pods work" });
});

test("a 503 explains that search is unavailable", async () => {
  respond(503, JSON.stringify({ detail: "Search is unavailable right now." }));
  await ask();
  expect(await screen.findByText(/search is unavailable/i)).toBeInTheDocument();
});

test("a 500 from the proxy says to check the backend", async () => {
  respond(500, "Internal Server Error", "text/plain");
  await ask();
  expect(await screen.findByText(/check that the backend is running on port 8000/i)).toBeInTheDocument();
});

test("a network failure says the app can't be reached", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
  await ask();
  expect(await screen.findByText(/couldn't reach engram/i)).toBeInTheDocument();
});

test("the form shows a loading state while asking", async () => {
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
  await ask();
  expect(screen.getByRole("button", { name: "Asking…" })).toBeDisabled();
  expect(screen.getByText(/searching your documents/i)).toBeInTheDocument();
});
