# Engram Frontend Redesign: Blueprint

**Status:** Approved on 2026-11-13.
**Parent documents:** `Plan.md` and `docs/specs/2026-11-07-phase-1-foundation-design.md` (§ "Ask screen" and "Sources screen").

This spec covers the frontend redesign only. Phases 2, 3 and 4 follow it, each with its own spec and plan.

## 1. Goal

Give Engram a distinctive, portfolio-grade frontend: a showpiece landing page and restyled Ask and Sources screens that share one visual identity, called Blueprint.

### Agreed understanding

**Decided by the project owner:**

- The frontend redesign comes first, then Phases 2 to 4 in `Plan.md` order.
- Scope is a new landing page plus restyled Ask and Sources screens.
- The main audience is recruiters and others judging a portfolio.
- The visual direction is Blueprint: light grid paper, monospace labels, hard edges, one orange-red signal colour, the retrieval pipeline as the hero image.
- The landing page structure is the eight sections in §4.

**Assumed, open to correction:**

- The landing page links to the public repository, `https://github.com/asw-beep/Engram`.
- The app keeps a dark variant, because the current app follows the system colour scheme.
- No backend change is part of this work.

### Success criteria

- A visitor understands what Engram is and how it works from the landing page alone.
- The page never claims something the code doesn't do. Parts that aren't built show as planned.
- Ask and Sources keep every current function, and their existing tests pass with only selector or route updates.
- The site works with JavaScript animation switched off, with reduced motion set, on a phone, and by keyboard.

## 2. Scope

**In scope:** the landing page at `/`; moving Ask to `/ask`; restyling Ask and Sources; shared design tokens, fonts and header; scroll and load animation; tests for new components.

**Out of scope:** new backend endpoints; streaming answers; login or tenant screens (Phase 3); WebGL or 3D; a CMS; analytics.

## 3. Visual identity

| Token | Light | Dark |
|---|---|---|
| `--paper` | `#eef0ea` | `#10161c` |
| `--ink` | `#14202b` | `#e6eae6` |
| `--muted` | `#3d4c59` | `#98a4ad` |
| `--signal` | `#ff4d1c` | `#ff6a3d` |
| `--grid` | ink at 7% | ink at 8% |
| `--field` | `#ffffff` | `#172029` |

- **Type:** Space Grotesk for headings and body, JetBrains Mono for labels, figures, code and buttons. Both load through `next/font/google`, which self-hosts them at build time. Labels are uppercase mono with wide tracking.
- **Shape:** 1px ink borders, square corners, no shadows, no gradients. Planned parts use a dashed border and muted text.
- **Grid paper:** a 40px line grid on the page background.
- **Signal colour:** used only for the thing that matters in a view: the cited answer node, citation markers, a running job, an error. Errors also carry text, never colour alone.
- **Figures:** sections are numbered like a spec (`01 — Problem`, `FIG. 1 — QUERY PATH`).

Text and signal colours must meet WCAG AA contrast against their backgrounds. Signal on paper is for large text, borders and filled blocks with white text, not for small body text.

## 4. Landing page

Route `/`. A server component page made of section components. Content comes from one data module (§6), not from strings scattered through components.

| # | Section | Content | Motion |
|---|---|---|---|
| 0 | Nav | Brand, section anchors, GitHub, "Ask →" | Hides on scroll down, returns on scroll up |
| 1 | Hero | "Retrieval you can inspect." Short description, two buttons, the query-path diagram (Query → Dense / BM25 → Fuse + rerank → Cited answer) | Headline reveals line by line. Diagram nodes and wires draw in sequence |
| 2 | Ticker | Source types: source code, design docs, ADRs, OpenAPI specs, incident reports. Types not yet ingested are marked planned | Continuous marquee, pauses on hover |
| 3 | 01 Problem | One large statement about scattered engineering knowledge | Words change from faint to ink as the section scrolls |
| 4 | 02 Pipeline | Ingestion stages (connect, parse, chunk, embed, index) and query stages (authenticate, retrieve, rerank, generate, verify), each with a two-sentence note | Section pins. Scrolling steps through stages, lighting the active node and swapping the note |
| 5 | 03 Specimen | A fixed sample answer with citation markers and its passages, clearly labelled "Sample answer" | Clicking a marker highlights it and shows the passage |
| 6 | 04 System | Five stores with roles, and three rules: tenant isolation, permissions before retrieval, no evidence no answer | Cards stagger in. Hover inverts a card |
| 7 | 05 Build log | The four phases with real status | A progress line draws to the current phase |
| 8 | Closing | "Ask it something." in oversized type, app and GitHub links | Type scales in. Button follows the cursor slightly |

On phones the pipeline section doesn't pin. It becomes a plain vertical list with every note visible.

### Honesty rule

Every stage, store, source type and phase in the data module has a status: `live` or `planned`. Planned items render dashed with a "planned" label. Today that means BM25, fusion, reranking, OpenSearch, Redis, source-code and OpenAPI ingestion, authentication, and Phases 2 to 4. When a phase lands, its items change status in the data module and nowhere else.

The page shows no evaluation numbers. The `Plan.md` §10.5 targets are not results, so they stay off the page until they are measured.

## 5. App screens

Ask and Sources share an app header (brand linking to `/`, Ask, Sources) and the Blueprint tokens. Their behaviour, copy for errors and outcomes, API calls and accessibility attributes stay as they are.

**Ask (`/ask`):**

- A labelled query field and a mono "Ask ↵" button.
- While asking, a staged progress line replaces the plain status text. The stages are cosmetic and time-based, because the API returns the answer in one response. The text stays "Searching your documents and checking citations…" for screen readers.
- The answer sits left with signal-coloured markers. The cited passage sits in a bordered panel to the right, sliding in when a marker is selected. It stacks below on narrow screens.
- Outcome notices (insufficient evidence, quota, model error) render as bordered notice blocks.

**Sources (`/sources`):**

- Upload and GitHub forms sit side by side in two bordered panels, stacked on narrow screens. The upload panel is a drop zone that also keeps the file input.
- Jobs render as ruled rows: status, source, counts, time, retry. A running job shows an indeterminate signal-coloured bar.
- Connected sources keep the sync button and the defer-embedding option.

The old `/` content moves to `/ask`. Nothing else links to the old route, so no redirect is needed.

## 6. Structure

```
frontend/
├── app/
│   ├── layout.tsx            fonts, tokens, <html>
│   ├── globals.css           tokens, base, shared components
│   ├── page.tsx              landing page
│   ├── landing.css           landing-only styles
│   └── (app)/
│       ├── layout.tsx        app header
│       ├── ask/page.tsx
│       └── sources/page.tsx
├── components/
│   ├── landing/              Nav, Hero, QueryDiagram, Ticker, Problem,
│   │                         Pipeline, Specimen, System, BuildLog, Closing
│   ├── motion/               SmoothScroll, Reveal, useReducedMotion
│   └── (existing)            AskForm, AnswerView, UploadForm,
│                             GithubSourceForm, JobList
└── lib/
    ├── api.ts                unchanged
    └── system.ts             stages, stores, rules, phases, source types,
                              sample answer; each item has a status
```

Each landing section is its own component that takes its data as props. `Specimen` reuses `splitAnswer` from `AnswerView` so the sample and the real answer parse markers the same way.

## 7. Motion

**Libraries:** GSAP with ScrollTrigger and `@gsap/react` for scroll-driven and timeline animation, and Lenis for smooth scrolling on the landing page only.

| Option | Verdict |
|---|---|
| GSAP + ScrollTrigger + Lenis | Chosen. Pinning, scrubbed timelines and sequenced drawing are what this design needs, and it is the standard toolset for this kind of site |
| Motion (Framer Motion) | Good for component transitions, weaker for pinned, scrubbed sequences |
| CSS scroll-driven animations only | No dependency, but browser support is incomplete and pinning with stepped content is awkward |

**Rules:**

- Content is in the server-rendered HTML and visible by default. Animation code sets starting states from JavaScript, so a visitor without JavaScript, or before hydration, sees the full page.
- `prefers-reduced-motion: reduce` turns off smooth scrolling, pinning, the marquee and all reveals. Everything shows in its final state.
- Animations use transforms and opacity only. Animation components are client components; section content stays in server components where possible.
- The app screens use small CSS transitions only. They don't load GSAP or Lenis.

## 8. Error handling and accessibility

- The landing page makes no API calls, so it renders when the backend is down.
- App screens keep their current error messages and `aria-live` regions.
- The pinned pipeline is also reachable by keyboard: each stage is a button, and focusing or pressing one selects it.
- The marquee is `aria-hidden` and the same list exists as plain text for screen readers.
- Focus outlines stay visible on every interactive element.

## 9. Testing

| Area | Check |
|---|---|
| `lib/system.ts` | Every item has a valid status. The sample answer's markers all resolve to sample passages |
| `Specimen` | Selecting a marker shows its passage; selecting again hides it |
| `Pipeline` | Choosing a stage shows its note. Planned stages carry the planned label |
| `BuildLog`, `System`, `QueryDiagram` | Live and planned items render with the right label |
| Reduced motion | With reduced motion set, components render final content and start no animation |
| Existing tests | `AnswerView`, `AskForm`, `UploadForm`, `GithubSourceForm`, `JobList` and the Sources page keep passing |
| Build | `npm run lint`, `npm run test` and `npm run build` pass |
| By hand | The landing page and both app screens checked in a browser at desktop and phone widths, light and dark, with the backend running |

GSAP and Lenis are mocked in unit tests. Animation itself is checked by hand in the browser.

## 10. Downloads

`npm install` runs with `npm_config_cache=E:/Projects/Engram/data/npm-cache`. Fonts are fetched by `next/font` at build time into the project's `.next` directory. Nothing goes to C:.
