"use client";

import { useState } from "react";

import type { Citation, Outcome, QuestionResponse } from "@/lib/api";

const MESSAGES: Record<Exclude<Outcome, "answered" | "quota_exhausted">, string> = {
  insufficient_evidence:
    "There's not enough evidence in your documents to answer this. Try a more specific question, or add the documents that cover it.",
  unverifiable:
    "The model couldn't produce a verifiable answer, because none of its claims pointed to a passage. Try asking again or rephrasing.",
  llm_error: "AI answers are unavailable right now because the model didn't respond. Try again in a few minutes.",
};

const QUOTA_NOTE =
  "Today's free AI answers are used up, so AI answers are unavailable until the limit resets. These passages match your question best:";

export default function AnswerView({ response }: { response: QuestionResponse }) {
  if (response.outcome === "quota_exhausted") {
    return (
      <section className="result">
        <p className="notice">{QUOTA_NOTE}</p>
        <ol className="passages">
          {response.passages.map((passage) => (
            <li key={passage.marker}>
              <SourceNote citation={passage} />
            </li>
          ))}
        </ol>
      </section>
    );
  }
  if (response.outcome !== "answered" || response.answer === null) {
    const outcome = response.outcome === "answered" ? "unverifiable" : response.outcome;
    return <p className="notice result">{MESSAGES[outcome]}</p>;
  }
  return <Answer answer={response.answer} citations={response.citations} />;
}

function Answer({ answer, citations }: { answer: string; citations: Citation[] }) {
  const [selected, setSelected] = useState<number | null>(null);
  const byMarker = new Map(citations.map((citation) => [citation.marker, citation]));
  const shown = selected === null ? undefined : byMarker.get(selected);

  return (
    <section className="result answer">
      <p className="answer-text">
        {splitAnswer(answer, byMarker).map((segment, index) =>
          typeof segment === "string" ? (
            segment
          ) : (
            <button
              key={index}
              type="button"
              className="marker"
              aria-pressed={segment === selected}
              aria-controls="source-margin"
              onClick={() => setSelected(segment === selected ? null : segment)}
            >
              [{segment}]
            </button>
          ),
        )}
      </p>
      <aside id="source-margin" className="margin" aria-live="polite">
        {shown ? (
          <SourceNote citation={shown} highlighted />
        ) : (
          <p className="hint">Select a marker to read the passage it cites.</p>
        )}
      </aside>
    </section>
  );
}

const MARKER = /\[(\d+)\]/g;

/**
 * Split the answer into plain strings and citation numbers. Only markers with a citation
 * become numbers, and a marker right after a word character, as in items[1], stays text.
 */
export function splitAnswer(answer: string, citations: Map<number, Citation>): (string | number)[] {
  const segments: (string | number)[] = [];
  let last = 0;
  for (const match of answer.matchAll(MARKER)) {
    const start = match.index ?? 0;
    const marker = Number(match[1]);
    if (!citations.has(marker) || /\w/.test(answer.charAt(start - 1))) continue;
    if (start > last) segments.push(answer.slice(last, start));
    segments.push(marker);
    last = start + match[0].length;
  }
  if (last < answer.length) segments.push(answer.slice(last));
  return segments;
}

export function SourceNote({ citation, highlighted = false }: { citation: Citation; highlighted?: boolean }) {
  const details = [citation.source_name, location(citation), revision(citation.revision)].filter(Boolean);
  const url = safeUrl(citation.url);
  return (
    <article className={highlighted ? "source-note highlighted" : "source-note"}>
      <p className="source-path">
        <span className="source-marker">[{citation.marker}]</span> <code>{citation.document_path}</code>
      </p>
      {citation.heading_path.length > 0 && (
        <p className="source-headings">{citation.heading_path.join(" › ")}</p>
      )}
      <p className="source-details">{details.join(", ")}</p>
      <blockquote className="source-snippet">{citation.snippet}</blockquote>
      {url && (
        <a className="source-link" href={url} target="_blank" rel="noopener noreferrer">
          Open in the repository
        </a>
      )}
    </article>
  );
}

function location(citation: Citation): string | null {
  const range = (label: string, start: number | null, end: number | null) => {
    if (start === null) return null;
    return end === null || end === start ? `${label} ${start}` : `${label}s ${start}–${end}`;
  };
  return range("page", citation.page_start, citation.page_end) ?? range("line", citation.start_line, citation.end_line);
}

function revision(value: string | null): string | null {
  return value ? `revision ${value.slice(0, 12)}` : null;
}

/** Only the backend builds links, and only https links are followed. */
function safeUrl(url: string | null): string | null {
  return url !== null && url.startsWith("https://") ? url : null;
}
