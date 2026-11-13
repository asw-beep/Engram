import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";

import BuildLog from "@/components/landing/BuildLog";
import QueryDiagram from "@/components/landing/QueryDiagram";
import System from "@/components/landing/System";
import Ticker from "@/components/landing/Ticker";
import { PHASES, QUERY_PATH, RULES, SOURCE_TYPES, STORES } from "@/lib/system";

/** The list item or card that holds the given text. */
function itemWith(text: string): HTMLElement {
  const item = screen.getByText(text).closest("li");
  if (!item) throw new Error(`${text} is not inside a list item`);
  return item;
}

test("the query diagram marks only the parts that are not built as planned", () => {
  render(<QueryDiagram path={QUERY_PATH} />);
  expect(within(itemWith("BM25")).getByText("planned")).toBeInTheDocument();
  expect(within(itemWith("Fuse + rerank")).getByText("planned")).toBeInTheDocument();
  expect(within(itemWith("Dense")).queryByText("planned")).not.toBeInTheDocument();
  expect(within(itemWith("Cited answer")).queryByText("planned")).not.toBeInTheDocument();
});

test("the system section marks OpenSearch and Redis as planned and lists three rules", () => {
  render(<System stores={STORES} rules={RULES} />);
  expect(within(itemWith("OpenSearch")).getByText("planned")).toBeInTheDocument();
  expect(within(itemWith("Redis")).getByText("planned")).toBeInTheDocument();
  expect(within(itemWith("PostgreSQL")).queryByText("planned")).not.toBeInTheDocument();
  expect(screen.getAllByText(/^Rule \d+$/)).toHaveLength(3);
});

test("the build log shows four phases, three of them planned", () => {
  render(<BuildLog phases={PHASES} />);
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
  expect(screen.getAllByText("planned")).toHaveLength(3);
  expect(within(itemWith("Foundation")).getByText("built")).toBeInTheDocument();
});

test("the ticker exposes each source type once to assistive technology", () => {
  render(<Ticker types={SOURCE_TYPES} />);
  // The second copy that makes the loop seamless is hidden from the accessibility tree.
  const items = screen.getAllByRole("listitem");
  expect(items).toHaveLength(SOURCE_TYPES.length);
  const code = items.find((item) => item.textContent?.includes("Source code"));
  expect(code).toHaveTextContent("planned");
});
