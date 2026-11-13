"use client";

import { type FormEvent, type KeyboardEvent, useState } from "react";

import AnswerView from "@/components/AnswerView";
import AskProgress from "@/components/AskProgress";
import { ApiError, askQuestion, type QuestionResponse } from "@/lib/api";

const MAX_QUESTION_CHARS = 2000;

type State =
  | { status: "idle" }
  | { status: "asking" }
  | { status: "answered"; response: QuestionResponse }
  | { status: "failed"; message: string };

export default function AskForm() {
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<State>({ status: "idle" });
  const asking = state.status === "asking";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    setState({ status: "asking" });
    try {
      setState({ status: "answered", response: await askQuestion(trimmed) });
    } catch (error) {
      setState({ status: "failed", message: describeError(error) });
    }
  }

  // Enter asks, and Shift+Enter starts a new line.
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <>
      <form className="ask" onSubmit={submit}>
        <label htmlFor="question" className="visually-hidden">
          Question
        </label>
        <textarea
          id="question"
          name="question"
          rows={3}
          maxLength={MAX_QUESTION_CHARS}
          placeholder="How does the scheduler decide where a pod runs?"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className="ask-button" disabled={asking || !question.trim()}>
          {asking ? (
            "Asking…"
          ) : (
            <>
              Ask <span aria-hidden="true">↵</span>
            </>
          )}
        </button>
      </form>
      <div className="outcome" aria-live="polite" aria-busy={asking}>
        {asking && <AskProgress />}
        {state.status === "failed" && <p className="notice error">{state.message}</p>}
        {state.status === "answered" && <AnswerView response={state.response} />}
      </div>
    </>
  );
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 503) {
      return "Search is unavailable because the database or vector store isn't responding. Try again shortly.";
    }
    // The Next.js proxy also answers 500 when the backend isn't running.
    if (error.status >= 500) {
      return `The Engram API didn't answer (HTTP ${error.status}). Check that the backend is running on port 8000, then try again.`;
    }
    return `The question couldn't be answered: ${error.message}`;
  }
  return "Couldn't reach Engram. Check your connection and that the app is still running.";
}
