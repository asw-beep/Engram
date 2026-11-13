import { expect, test } from "vitest";

import {
  INGESTION_STAGES,
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

test("parts that are not built are marked planned", () => {
  expect(QUERY_PATH.sparse.status).toBe("planned");
  expect(QUERY_PATH.fuse.status).toBe("planned");
  expect(STORES.find((store) => store.name === "OpenSearch")?.status).toBe("planned");
  expect(PHASES.map((phase) => phase.status)).toEqual(["live", "planned", "planned", "planned"]);
});
