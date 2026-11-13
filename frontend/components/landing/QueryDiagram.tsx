import StatusTag from "@/components/landing/StatusTag";
import type { DiagramNode } from "@/lib/system";

type Path = Record<"query" | "dense" | "sparse" | "fuse" | "answer", DiagramNode>;

/** FIG. 1: a question's path to a cited answer. Planned steps are drawn dashed. */
export default function QueryDiagram({ path }: { path: Path }) {
  return (
    <figure className="qd">
      <ol className="qd-steps" aria-label="Query path">
        <Node node={path.query} />
        <Wire />
        <li className="qd-split">
          <ol className="qd-pair" aria-label="Retrieval">
            <Node node={path.dense} />
            <Node node={path.sparse} />
          </ol>
        </li>
        <Wire />
        <Node node={path.fuse} />
        <Wire />
        <Node node={path.answer} hot />
      </ol>
      <figcaption className="label">Fig. 1 — Query path</figcaption>
    </figure>
  );
}

function Node({ node, hot = false }: { node: DiagramNode; hot?: boolean }) {
  const classes = ["qd-node", node.status === "planned" && "planned", hot && "qd-hot"].filter(Boolean);
  return (
    <li className={classes.join(" ")} data-anim="node">
      <span className="qd-label">{node.label}</span>
      <StatusTag status={node.status} />
      <span className="qd-index" aria-hidden="true">
        {node.index}
      </span>
    </li>
  );
}

function Wire() {
  return (
    <li className="qd-wire" aria-hidden="true">
      <span data-anim="wire" />
    </li>
  );
}
