/**
 * What the landing page says about Engram. Every part carries a status, and the page draws
 * planned parts dashed. When a phase lands, change its statuses here and nowhere else.
 */

import type { Citation } from "@/lib/api";

export type Status = "live" | "planned";
export type Stage = { id: string; label: string; note: string; status: Status };
export type DiagramNode = { id: string; label: string; index: string; status: Status };
export type Store = { name: string; role: string; status: Status };
export type Rule = { id: string; title: string; text: string };
export type Phase = { id: string; name: string; summary: string; status: Status };
export type SourceType = { label: string; status: Status };

export const GITHUB_URL = "https://github.com/asw-beep/Engram";

export const QUERY_PATH = {
  query: { id: "query", label: "Query", index: "01", status: "live" },
  dense: { id: "dense", label: "Dense", index: "02a", status: "live" },
  sparse: { id: "sparse", label: "BM25", index: "02b", status: "planned" },
  fuse: { id: "fuse", label: "Fuse + rerank", index: "03", status: "planned" },
  answer: { id: "answer", label: "Cited answer", index: "04", status: "live" },
} satisfies Record<string, DiagramNode>;

export const INGESTION_STAGES: Stage[] = [
  {
    id: "connect",
    label: "Connect",
    note: "Connectors share one interface, so a new source plugs in without touching the rest. File uploads and public GitHub repositories work today.",
    status: "live",
  },
  {
    id: "parse",
    label: "Parse",
    note: "Markdown, PDF and Word files are read into one normalised structure of headings, text and page or line positions. Each document keeps its tenant and access metadata from this point on.",
    status: "live",
  },
  {
    id: "chunk",
    label: "Chunk",
    note: "Documents are split along their own structure, by heading and section, not into fixed-size windows. Each chunk remembers its heading path so a citation can say where it came from.",
    status: "live",
  },
  {
    id: "embed",
    label: "Embed",
    note: "BGE-M3 turns each chunk into a dense vector, on the local GPU or in bulk on Kaggle. The model version is stored with the vectors so content can be re-embedded when the model changes.",
    status: "live",
  },
  {
    id: "index",
    label: "Index",
    note: "PostgreSQL holds the canonical record and Qdrant holds the vectors as a rebuildable projection. Content hashes make jobs idempotent, so unchanged documents are skipped.",
    status: "live",
  },
];

export const QUERY_STAGES: Stage[] = [
  {
    id: "authenticate",
    label: "Authenticate",
    note: "Sign-in and per-user permissions arrive with the enterprise phase. The schema already carries tenant and access fields on every record, and today everything runs in one default tenant.",
    status: "planned",
  },
  {
    id: "retrieve",
    label: "Retrieve",
    note: "The question is embedded and matched against Qdrant with the tenant filter applied inside the search. Permissions are checked again in PostgreSQL before any passage is used.",
    status: "live",
  },
  {
    id: "rerank",
    label: "Rerank",
    note: "A keyword index and a cross-encoder reranker will join dense search, merged with Reciprocal Rank Fusion. Until then, results come from dense retrieval alone.",
    status: "planned",
  },
  {
    id: "generate",
    label: "Generate",
    note: "The best passages go to the model as clearly delimited data, with instructions never to follow anything written inside them. A fallback model takes over if the first one fails.",
    status: "live",
  },
  {
    id: "verify",
    label: "Verify",
    note: "Every citation marker in the answer must point to a passage that was actually retrieved. If the evidence is too weak, Engram says so and gives no answer.",
    status: "live",
  },
];

export const STORES: Store[] = [
  { name: "PostgreSQL", role: "Canonical metadata: tenants, sources, documents, chunks, jobs", status: "live" },
  { name: "Qdrant", role: "Dense vectors, linked to chunk IDs", status: "live" },
  { name: "OpenSearch", role: "BM25 keyword index", status: "planned" },
  { name: "Redis", role: "Caching and job coordination", status: "planned" },
  { name: "Object store", role: "Original files, on a disk volume today", status: "live" },
];

export const RULES: Rule[] = [
  {
    id: "01",
    title: "Tenant isolation",
    text: "Every record carries its tenant, and every query, search and cache entry is bounded by it.",
  },
  {
    id: "02",
    title: "Permissions before retrieval",
    text: "Access is filtered before the search runs and checked again when the context is assembled.",
  },
  {
    id: "03",
    title: "No evidence, no answer",
    text: "Citations must resolve to passages that were retrieved. Without enough evidence, there is no answer.",
  },
];

export const PHASES: Phase[] = [
  {
    id: "1",
    name: "Foundation",
    summary: "Ingestion, structure-aware chunking, dense retrieval, cited answers, production containers",
    status: "live",
  },
  {
    id: "2",
    name: "Advanced retrieval",
    summary: "Keyword index, hybrid search with rank fusion, reranking, evaluation dataset",
    status: "planned",
  },
  {
    id: "3",
    name: "Enterprise",
    summary: "Sign-in, tenancy and access control, background workers, incremental sync",
    status: "planned",
  },
  {
    id: "4",
    name: "Deployment",
    summary: "Cloud deployment, CI/CD, observability, load testing",
    status: "planned",
  },
];

export const SOURCE_TYPES: SourceType[] = [
  { label: "Design docs", status: "live" },
  { label: "ADRs", status: "live" },
  { label: "Incident reports", status: "live" },
  { label: "Source code", status: "planned" },
  { label: "OpenAPI specs", status: "planned" },
];

const SCHEDULER_DOC = "content/en/docs/concepts/scheduling-eviction/kube-scheduler.md";

function sampleCitation(marker: number, heading: string, snippet: string): Citation {
  return {
    marker,
    document_path: SCHEDULER_DOC,
    source_name: "kubernetes/website",
    heading_path: ["Kubernetes Scheduler", heading],
    start_line: null,
    end_line: null,
    page_start: null,
    page_end: null,
    revision: null,
    snippet,
    url: `https://github.com/kubernetes/website/blob/main/${SCHEDULER_DOC}`,
  };
}

/** A fixed example for the landing page. It is not a live answer, and the page says so. */
export const SAMPLE: { question: string; answer: string; citations: Citation[] } = {
  question: "How does the scheduler decide where a pod runs?",
  answer:
    "The scheduler picks a node in two steps. It first filters out the nodes that can't run the pod, which leaves the feasible nodes [1]. It then scores the feasible nodes and assigns the pod to the one with the highest score, choosing at random when several tie [2].",
  citations: [
    sampleCitation(
      1,
      "Node selection in kube-scheduler",
      "The filtering step finds the set of Nodes where it's feasible to schedule the Pod. After this step, the node list contains any suitable Nodes.",
    ),
    sampleCitation(
      2,
      "Node selection in kube-scheduler",
      "In the scoring step, the scheduler ranks the remaining nodes to choose the most suitable Pod placement. kube-scheduler assigns the Pod to the Node with the highest ranking. If there is more than one node with equal scores, kube-scheduler selects one of these at random.",
    ),
  ],
};
