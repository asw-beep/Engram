import type { Phase } from "@/lib/system";

export default function BuildLog({ phases }: { phases: Phase[] }) {
  const built = phases.filter((phase) => phase.status === "live").length;
  return (
    <section id="build-log" className="l-section build-log">
      <p className="label section-label">05 — Build log</p>
      <h2 className="section-title">Built in order, reported as it stands.</h2>
      <div className="bl-rail" aria-hidden="true">
        <span data-anim="build-line" style={{ width: `${(built / phases.length) * 100}%` }} />
      </div>
      <ol className="bl-phases">
        {phases.map((phase) => (
          <li key={phase.id} className={phase.status === "planned" ? "bl-phase bl-planned" : "bl-phase"}>
            <span className="label bl-head">
              <span>Phase {phase.id}</span>
              <span className="bl-status">{phase.status === "live" ? "built" : "planned"}</span>
            </span>
            <h3 className="bl-name">{phase.name}</h3>
            <p className="card-text">{phase.summary}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
