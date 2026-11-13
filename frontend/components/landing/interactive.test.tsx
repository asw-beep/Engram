import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import Pipeline from "@/components/landing/Pipeline";
import Specimen from "@/components/landing/Specimen";
import { INGESTION_STAGES, QUERY_STAGES, SAMPLE } from "@/lib/system";

const note = (id: string) => [...INGESTION_STAGES, ...QUERY_STAGES].find((stage) => stage.id === id)!.note;

function renderPipeline() {
  render(<Pipeline ingestion={INGESTION_STAGES} query={QUERY_STAGES} />);
}

test("the first ingestion stage is selected to begin with", () => {
  renderPipeline();
  expect(screen.getByRole("button", { name: /Connect/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByText(note("connect"))).toBeVisible();
  expect(screen.getByText(note("chunk"))).not.toBeVisible();
});

test("choosing a stage shows its note and hides the previous one", async () => {
  renderPipeline();
  await userEvent.click(screen.getByRole("button", { name: /Chunk/ }));
  expect(screen.getByText(note("chunk"))).toBeVisible();
  expect(screen.getByText(note("connect"))).not.toBeVisible();
});

test("a stage can be chosen from the keyboard", async () => {
  renderPipeline();
  screen.getByRole("button", { name: /Verify/ }).focus();
  await userEvent.keyboard("{Enter}");
  expect(screen.getByText(note("verify"))).toBeVisible();
});

test("a stage that is not built says planned", () => {
  renderPipeline();
  expect(within(screen.getByRole("button", { name: /Rerank/ })).getByText("planned")).toBeInTheDocument();
  expect(within(screen.getByRole("button", { name: /Chunk/ })).queryByText("planned")).not.toBeInTheDocument();
});

test("with reduced motion every stage's note is shown", () => {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("prefers-reduced-motion"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  renderPipeline();
  for (const stage of [...INGESTION_STAGES, ...QUERY_STAGES]) {
    expect(screen.getByText(stage.note)).toBeVisible();
  }
});

test("the specimen is labelled as a sample and starts with no passage", () => {
  render(<Specimen sample={SAMPLE} />);
  expect(screen.getByText("Sample answer")).toBeVisible();
  expect(screen.getByText("Select a marker to read the passage it cites.")).toBeVisible();
  expect(screen.queryByText(SAMPLE.citations[0].snippet)).not.toBeInTheDocument();
});

test("selecting a marker shows its passage, and selecting it again hides it", async () => {
  render(<Specimen sample={SAMPLE} />);
  const marker = screen.getByRole("button", { name: "[1]" });
  await userEvent.click(marker);
  expect(screen.getByText(SAMPLE.citations[0].snippet)).toBeVisible();
  expect(marker).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(marker);
  expect(screen.queryByText(SAMPLE.citations[0].snippet)).not.toBeInTheDocument();
});
