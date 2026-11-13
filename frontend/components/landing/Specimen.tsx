"use client";

import { useState } from "react";

import { SourceNote, splitAnswer } from "@/components/AnswerView";
import type { Citation } from "@/lib/api";

type Sample = { question: string; answer: string; citations: Citation[] };

/** A fixed example of a cited answer that behaves like the real Ask screen. */
export default function Specimen({ sample }: { sample: Sample }) {
  const [selected, setSelected] = useState<number | null>(null);
  const byMarker = new Map(sample.citations.map((citation) => [citation.marker, citation]));
  const shown = selected === null ? undefined : byMarker.get(selected);

  return (
    <section id="specimen" className="l-section specimen">
      <p className="label section-label">03 — Specimen</p>
      <h2 className="section-title">Every claim carries its source.</h2>
      <p className="section-lede">
        Select a marker in the answer to read the passage behind it. The real app works the same
        way on your own documents.
      </p>
      <div className="sp-sheet">
        <div className="sp-answer">
          <p className="sp-tags">
            <span className="status-tag">Sample answer</span>
          </p>
          <p className="sp-question">
            <span className="label" aria-hidden="true">
              Q{" "}
            </span>
            {sample.question}
          </p>
          <p className="answer-text">
            {splitAnswer(sample.answer, byMarker).map((segment, index) =>
              typeof segment === "string" ? (
                segment
              ) : (
                <button
                  key={index}
                  type="button"
                  className="marker"
                  aria-pressed={segment === selected}
                  aria-controls="specimen-source"
                  onClick={() => setSelected(segment === selected ? null : segment)}
                >
                  [{segment}]
                </button>
              ),
            )}
          </p>
        </div>
        <aside id="specimen-source" className="sp-source" aria-live="polite">
          {shown ? (
            <SourceNote key={shown.marker} citation={shown} highlighted />
          ) : (
            <p className="hint">Select a marker to read the passage it cites.</p>
          )}
        </aside>
      </div>
    </section>
  );
}
