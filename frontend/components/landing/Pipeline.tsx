"use client";

import { useState } from "react";

import StatusTag from "@/components/landing/StatusTag";
import { useReducedMotion } from "@/components/motion/useReducedMotion";
import type { Stage } from "@/lib/system";

/**
 * The two paths through Engram, one stage at a time. Selecting a stage shows its note.
 * With reduced motion every note is shown, and on narrow screens the stylesheet does the same.
 */
export default function Pipeline({ ingestion, query }: { ingestion: Stage[]; query: Stage[] }) {
  const [active, setActive] = useState(0);
  const showAll = useReducedMotion();
  const total = ingestion.length + query.length;
  const groups = [
    { name: "Ingestion", stages: ingestion, offset: 0 },
    { name: "Query", stages: query, offset: ingestion.length },
  ];

  return (
    <section id="pipeline" className="l-section pipeline" data-anim="pipeline">
      <p className="label section-label">02 — Pipeline</p>
      <h2 className="section-title">Two paths, ten stages.</h2>
      <p className="section-lede">
        One path takes documents in. The other answers a question. Step through them to see what
        each stage does today.
      </p>
      <div className="pl-body" data-show-all={showAll}>
        {groups.map((group) => (
          <div key={group.name} className="pl-group">
            <h3 className="label pl-group-name">{group.name}</h3>
            <ol className="pl-row">
              {group.stages.map((stage, position) => {
                const index = group.offset + position;
                const selected = index === active;
                return (
                  <li key={stage.id} className="pl-stage">
                    <button
                      type="button"
                      className={stage.status === "planned" ? "pl-button planned" : "pl-button"}
                      aria-pressed={selected}
                      data-stage-index={index}
                      onClick={() => setActive(index)}
                    >
                      <span className="pl-number" aria-hidden="true">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <span className="pl-label">{stage.label}</span>
                      <StatusTag status={stage.status} />
                    </button>
                    <div className="pl-note" hidden={!selected && !showAll}>
                      <p className="label pl-note-head">
                        {group.name} · stage {index + 1} of {total}
                      </p>
                      <p className="pl-note-title" aria-hidden="true">
                        {stage.label}
                      </p>
                      <p className="pl-note-text">{stage.note}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        ))}
      </div>
    </section>
  );
}
