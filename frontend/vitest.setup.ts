import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// Testing Library only cleans up on its own when test globals are enabled.
afterEach(cleanup);

// jsdom has no matchMedia. Tests that need a matching query restub it.
beforeEach(() => {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});

// Animation is checked by hand in the browser, so the libraries are inert in unit tests.
vi.mock("gsap", () => {
  const gsap = {
    registerPlugin: vi.fn(),
    from: vi.fn(),
    fromTo: vi.fn(),
    to: vi.fn(),
    set: vi.fn(),
    timeline: vi.fn(),
    matchMedia: vi.fn(),
    quickTo: vi.fn(() => vi.fn()),
    ticker: { add: vi.fn(), remove: vi.fn(), lagSmoothing: vi.fn() },
  };
  return { default: gsap, gsap };
});
vi.mock("gsap/ScrollTrigger", () => ({ ScrollTrigger: { update: vi.fn(), refresh: vi.fn() } }));
vi.mock("@gsap/react", () => ({ useGSAP: vi.fn() }));
vi.mock("lenis", () => ({
  default: vi.fn(function Lenis() {
    return { on: vi.fn(), raf: vi.fn(), destroy: vi.fn() };
  }),
}));
