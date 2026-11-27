import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test } from "vitest";

import {
  INGESTION_STAGES,
  MEASURED,
  PHASES,
  QUERY_PATH,
  QUERY_STAGES,
  SAMPLE,
  SOURCE_TYPES,
  STORES,
} from "@/lib/system";

test("every item has a valid status", () => {
  const items = [
    ...Object.values(QUERY_PATH),
    ...INGESTION_STAGES,
    ...QUERY_STAGES,
    ...STORES,
    ...PHASES,
    ...SOURCE_TYPES,
  ];
  for (const item of items) expect(["live", "planned"]).toContain(item.status);
});

test("every marker in the sample answer has a citation, and every citation is used", () => {
  const used = [...SAMPLE.answer.matchAll(/\[(\d+)\]/g)].map((match) => Number(match[1]));
  const have = SAMPLE.citations.map((citation) => citation.marker);
  expect(used.length).toBeGreaterThan(0);
  expect(new Set(used)).toEqual(new Set(have));
});

test("Phase 2's parts are live and only later phases' parts are planned", () => {
  expect(Object.values(QUERY_PATH).map((node) => node.status)).not.toContain("planned");
  expect(QUERY_STAGES.find((stage) => stage.id === "rerank")?.status).toBe("live");
  expect(QUERY_STAGES.find((stage) => stage.id === "authenticate")?.status).toBe("planned");
  expect(STORES.find((store) => store.name === "OpenSearch")?.status).toBe("live");
  expect(STORES.find((store) => store.name === "Redis")?.status).toBe("planned");
  expect(PHASES.map((phase) => phase.status)).toEqual(["live", "live", "planned", "planned"]);
});

type Summary = { answerable: number; overall: Record<string, number> };
type Result = { summary: Summary; corpus: { documents: number } };

function result(config: string): Result {
  const file = resolve(process.cwd(), "../backend/eval/results", `${config}.json`);
  return JSON.parse(readFileSync(file, "utf-8")) as Result;
}

test("the measured numbers are the test summaries in the result files", () => {
  expect(MEASURED.rows.map((row) => row.config)).toEqual([
    "dense",
    "hybrid",
    "dense_rerank",
    "hybrid_rerank",
  ]);
  for (const row of MEASURED.rows) {
    const { summary, corpus } = result(row.config);
    expect(row.recallAt5).toBeCloseTo(summary.overall["recall@5"], 3);
    expect(row.mrrAt10).toBeCloseTo(summary.overall["mrr@10"], 3);
    expect(row.ndcgAt10).toBeCloseTo(summary.overall["ndcg@10"], 3);
    expect(MEASURED.questions).toBe(summary.answerable);
    expect(MEASURED.documents).toBe(corpus.documents);
  }
  expect(MEASURED.rows.map((row) => row.config)).toContain(MEASURED.served);
});
