import { render, screen } from "@testing-library/react";
import Lenis from "lenis";
import { beforeEach, expect, test, vi } from "vitest";

import Reveal from "@/components/motion/Reveal";
import SmoothScroll from "@/components/motion/SmoothScroll";

function reduceMotion() {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("prefers-reduced-motion"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

beforeEach(() => {
  vi.mocked(Lenis).mockClear();
});

test("revealed content is in the page with no hidden starting state", () => {
  render(<Reveal>Retrieval you can inspect.</Reveal>);
  const content = screen.getByText("Retrieval you can inspect.");
  expect(content).toBeVisible();
  expect(content).not.toHaveAttribute("style");
});

test("a reveal renders the element it is asked for", () => {
  render(<Reveal as="h2">Pipeline</Reveal>);
  expect(screen.getByRole("heading", { level: 2, name: "Pipeline" })).toBeInTheDocument();
});

test("smooth scrolling starts once when motion is allowed", () => {
  render(<SmoothScroll>page</SmoothScroll>);
  expect(screen.getByText("page")).toBeInTheDocument();
  expect(Lenis).toHaveBeenCalledTimes(1);
});

test("smooth scrolling stays off when the visitor asks for reduced motion", () => {
  reduceMotion();
  render(<SmoothScroll>page</SmoothScroll>);
  expect(screen.getByText("page")).toBeInTheDocument();
  expect(Lenis).not.toHaveBeenCalled();
});
