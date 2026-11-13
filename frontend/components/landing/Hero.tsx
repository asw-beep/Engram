import Link from "next/link";

import QueryDiagram from "@/components/landing/QueryDiagram";
import { type Phase, QUERY_PATH } from "@/lib/system";

const HEADLINE = ["Retrieval", "you can", "inspect."];

export default function Hero({ githubUrl, phases }: { githubUrl: string; phases: Phase[] }) {
  const built = phases.filter((phase) => phase.status === "live").length;
  return (
    <section className="hero">
      <div className="hero-main">
        <div className="hero-copy">
          <p className="label hero-kicker">Permission-aware RAG for engineering knowledge</p>
          <h1 className="hero-title" aria-label={HEADLINE.join(" ")}>
            {HEADLINE.map((line, index) => (
              <span key={line} className="hero-line" aria-hidden="true">
                <span data-anim="hero-line" className={index === HEADLINE.length - 1 ? "hero-accent" : undefined}>
                  {line}
                </span>
              </span>
            ))}
          </h1>
          <p className="hero-lede">
            Engram reads design docs, ADRs and incident reports, then answers questions about them.
            Every claim points to the passage it came from, and every stage of the pipeline is open
            to inspection.
          </p>
          <div className="hero-actions">
            <Link href="/ask" className="button">
              Ask a question <span aria-hidden="true">→</span>
            </Link>
            <a href={githubUrl} className="button button-ghost" target="_blank" rel="noopener noreferrer">
              View on GitHub <span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
        <QueryDiagram path={QUERY_PATH} />
      </div>
      <dl className="title-block">
        <div>
          <dt>Project</dt>
          <dd>Engram</dd>
        </div>
        <div>
          <dt>Drawing</dt>
          <dd>Knowledge retrieval platform</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>
            Phase {built} of {phases.length} built
          </dd>
        </div>
        <div>
          <dt>Sheet</dt>
          <dd>01 / 05</dd>
        </div>
      </dl>
    </section>
  );
}
