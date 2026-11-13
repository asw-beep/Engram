import StatusTag from "@/components/landing/StatusTag";
import type { SourceType } from "@/lib/system";

/** A looping band of the source types Engram reads. The second copy only closes the loop. */
export default function Ticker({ types }: { types: SourceType[] }) {
  return (
    <div className="ticker">
      <div className="ticker-track">
        <Items types={types} />
        <Items types={types} hidden />
        <Items types={types} hidden />
      </div>
    </div>
  );
}

function Items({ types, hidden = false }: { types: SourceType[]; hidden?: boolean }) {
  return (
    <ul className="ticker-items" aria-hidden={hidden || undefined} aria-label={hidden ? undefined : "Sources Engram reads"}>
      {types.map((type) => (
        <li key={type.label} className={type.status === "planned" ? "ticker-planned" : undefined}>
          {type.label} <StatusTag status={type.status} />
        </li>
      ))}
    </ul>
  );
}
