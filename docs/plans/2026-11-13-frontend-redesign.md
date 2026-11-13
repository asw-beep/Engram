# Frontend Redesign (Blueprint) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a showpiece landing page and restyle the Ask and Sources screens in one visual identity, Blueprint, without changing what the app does.

**Architecture:** The landing page at `/` is a server component built from section components that read their content from `lib/system.ts`, where every item carries a `live` or `planned` status. Ask and Sources move into an `(app)` route group with a shared header. Animation lives in small client components that set starting states from JavaScript, so server-rendered content is visible without it.

**Tech Stack:** Next.js 16, React 19, TypeScript, plain CSS with custom properties, GSAP + ScrollTrigger + `@gsap/react`, Lenis, Vitest + Testing Library.

**Spec:** `docs/specs/2026-11-13-frontend-redesign-design.md`

## Global Constraints

- Run every command from `frontend/`. Any `npm install` runs with `npm_config_cache=E:/Projects/Engram/data/npm-cache`.
- Colours, light / dark: `--paper` `#eef0ea` / `#10161c`; `--ink` `#14202b` / `#e6eae6`; `--muted` `#3d4c59` / `#98a4ad`; `--signal` `#ff4d1c` / `#ff6a3d`; `--field` `#ffffff` / `#172029`; `--grid` ink at 7% / 8%.
- Fonts: Space Grotesk (text) and JetBrains Mono (labels, code, buttons) through `next/font/google`, exposed as `--font-text` and `--font-mono`.
- Shape: 1px ink borders, square corners, no shadows, no gradients. Planned items: dashed border, muted text, the visible word "planned".
- Signal colour is never the only carrier of meaning, and never used for small body text on paper.
- Content is visible in server-rendered HTML. Animation sets starting states from JavaScript only.
- `prefers-reduced-motion: reduce` disables smooth scrolling, pinning, the marquee and reveals.
- Animate transforms and opacity only. Ask and Sources must not import GSAP or Lenis.
- No evaluation numbers on any page. No backend change. `lib/api.ts` stays unchanged.
- Existing error and outcome copy, API calls and ARIA attributes in Ask and Sources stay as they are.
- Commits carry no co-author or tooling lines. Commit and push to `origin main` after each task.

## Review Focus

1. **JavaScript animation fails or is blocked:** the landing page must still show all content. Pinned by Task 3's `Reveal` test (children render with no inline hidden state when animation is mocked out).
2. **Reduced motion:** nothing animates and everything shows in its final state. Pinned by Task 3 (`SmoothScroll`, `Reveal`) and Task 5 (`Pipeline` shows every note).
3. **A sample-answer marker with no passage:** the specimen would show a dead button. Pinned by Task 2's data test.
4. **Keyboard-only visitor on the pipeline:** stages must be selectable without scrolling. Pinned by Task 5's `Pipeline` keyboard test.
5. **Long, unbroken content in the app** (a long document path, a long job error): rows must wrap, not overflow at phone width. Checked by hand in Task 9 at 375px, with `overflow-wrap: anywhere` on paths and errors in Tasks 7 and 8.

---

### Task 1: Tokens, fonts, routes and app header

**Files:**
- Modify: `package.json` (add `gsap`, `@gsap/react`, `lenis`), `app/layout.tsx`, `app/globals.css`, `vitest.setup.ts`
- Create: `app/(app)/layout.tsx`, `app/(app)/ask/page.tsx`
- Move: `app/sources/page.tsx` → `app/(app)/sources/page.tsx`, `app/sources/page.test.tsx` → `app/(app)/sources/page.test.tsx` (update its import path)
- Replace: `app/page.tsx` with a placeholder landing page (heading "Engram" and a link to `/ask`) until Task 4

**Interfaces:**
- Produces: CSS custom properties from Global Constraints plus `--font-text`, `--font-mono`; shared classes `.label` (uppercase mono, 0.08em tracking), `.button`, `.button-ghost`, `.panel` (1px ink border, paper background), `.planned` (dashed border, muted), `.visually-hidden`. `app/(app)/layout.tsx` renders `<header class="app-header">` with brand link to `/` and nav links "Ask" (`/ask`) and "Sources" (`/sources`).
- `vitest.setup.ts` adds a `window.matchMedia` stub returning `matches: false`, and `vi.mock` for `gsap`, `gsap/ScrollTrigger`, `@gsap/react` (`useGSAP` as a no-op) and `lenis`.

- [ ] **Step 1:** Install: `npm_config_cache=E:/Projects/Engram/data/npm-cache npm install gsap @gsap/react lenis`.
- [ ] **Step 2:** Move the routes and update the test import. Run `npm test`. Expected: all existing tests pass.
- [ ] **Step 3:** Rewrite `app/layout.tsx` to load both fonts and drop the header; add `app/(app)/layout.tsx` with the header.
- [ ] **Step 4:** Rewrite `app/globals.css`: tokens (light, dark through `prefers-color-scheme`), 40px grid-paper background on `body`, base elements, shared classes, and restyled versions of every class the existing components use, so Ask and Sources render correctly before Tasks 7 and 8 refine them.
- [ ] **Step 5:** Run `npm test && npm run lint && npm run build`. Expected: all pass.
- [ ] **Step 6:** Commit `feat: add Blueprint tokens, fonts and app routes`, push.

### Task 2: System data module

**Files:**
- Create: `lib/system.ts`, `lib/system.test.ts`

**Interfaces:**
- Produces:

```ts
export type Status = "live" | "planned";
export type Stage = { id: string; label: string; note: string; status: Status };
export type DiagramNode = { id: string; label: string; index: string; status: Status };
export type Store = { name: string; role: string; status: Status };
export type Rule = { id: string; title: string; text: string };
export type Phase = { id: string; name: string; summary: string; status: Status };
export type SourceType = { label: string; status: Status };
export const GITHUB_URL = "https://github.com/asw-beep/Engram";
export const QUERY_PATH: { query: DiagramNode; dense: DiagramNode; sparse: DiagramNode; fuse: DiagramNode; answer: DiagramNode };
export const INGESTION_STAGES: Stage[]; // connect, parse, chunk, embed, index
export const QUERY_STAGES: Stage[];     // authenticate, retrieve, rerank, generate, verify
export const STORES: Store[];           // PostgreSQL, Qdrant, OpenSearch, Redis, Object store
export const RULES: Rule[];             // tenant isolation, permissions before retrieval, no evidence no answer
export const PHASES: Phase[];           // 1 Foundation, 2 Advanced retrieval, 3 Enterprise, 4 Deployment
export const SOURCE_TYPES: SourceType[];
export const SAMPLE: { question: string; answer: string; citations: Citation[] }; // Citation from lib/api
```

- Status today. Live: query, dense, answer nodes; all ingestion stages; retrieve, generate, verify; PostgreSQL, Qdrant, Object store; Phase 1; design docs, ADRs, incident reports (as Markdown, PDF, Word). Planned: sparse, fuse; authenticate, rerank; OpenSearch, Redis; Phases 2 to 4; source code, OpenAPI specs.
- Each stage note is two sentences that describe what the code does today (see `CLAUDE.md` Architecture), not targets. `SAMPLE` uses the Kubernetes scheduler question with two citations.

- [ ] **Step 1:** Write failing tests:

```ts
test("every item has a valid status", () => {
  const items = [...Object.values(QUERY_PATH), ...INGESTION_STAGES, ...QUERY_STAGES, ...STORES, ...PHASES, ...SOURCE_TYPES];
  for (const item of items) expect(["live", "planned"]).toContain(item.status);
});
test("every marker in the sample answer has a citation, and every citation is used", () => {
  const used = [...SAMPLE.answer.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1]));
  const have = SAMPLE.citations.map((c) => c.marker);
  expect(new Set(used)).toEqual(new Set(have));
});
test("parts that are not built are marked planned", () => {
  expect(QUERY_PATH.sparse.status).toBe("planned");
  expect(QUERY_PATH.fuse.status).toBe("planned");
  expect(STORES.find((s) => s.name === "OpenSearch")?.status).toBe("planned");
  expect(PHASES.map((p) => p.status)).toEqual(["live", "planned", "planned", "planned"]);
});
```

- [ ] **Step 2:** Run `npx vitest run lib/system.test.ts`. Expected: FAIL, module not found.
- [ ] **Step 3:** Write `lib/system.ts`.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit `feat: add system data for the landing page`, push.

### Task 3: Motion primitives

**Files:**
- Create: `components/motion/useReducedMotion.ts`, `components/motion/SmoothScroll.tsx`, `components/motion/Reveal.tsx`, `components/motion/motion.test.tsx`

**Interfaces:**
- Produces:
  - `useReducedMotion(): boolean`: `useSyncExternalStore` over `matchMedia("(prefers-reduced-motion: reduce)")`, `false` on the server.
  - `<SmoothScroll>{children}</SmoothScroll>`: client component. Unless motion is reduced, creates a Lenis instance, drives it from `gsap.ticker`, calls `ScrollTrigger.update` on scroll, and destroys it on unmount. Always renders children.
  - `<Reveal as?="div" delay?={0} className?>{children}</Reveal>`: client component. With motion allowed, `useGSAP` runs `gsap.from(el, { y: 24, autoAlpha: 0, duration: 0.7, delay, scrollTrigger: { trigger: el, start: "top 85%" } })`. Renders children with no inline style of its own.

- [ ] **Step 1:** Write failing tests: `Reveal` renders its children visibly with no `style` attribute; `SmoothScroll` renders children and does not construct Lenis when `matchMedia` reports reduced motion; it constructs Lenis once otherwise.
- [ ] **Step 2:** Run `npx vitest run components/motion`. Expected: FAIL.
- [ ] **Step 3:** Implement the three files.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit `feat: add motion primitives`, push.

### Task 4: Landing page, static sections

**Files:**
- Create: `components/landing/Nav.tsx`, `Hero.tsx`, `QueryDiagram.tsx`, `Ticker.tsx`, `Problem.tsx`, `System.tsx`, `BuildLog.tsx`, `Closing.tsx`, `StatusTag.tsx`, `components/landing/landing.test.tsx`, `app/landing.css`
- Modify: `app/page.tsx`

**Interfaces:**
- Consumes: everything from `lib/system.ts`; shared classes from Task 1.
- Produces: `<StatusTag status={Status} />` renders the text "planned" for planned items and nothing for live ones. Each section takes its data as props (`<QueryDiagram path={QUERY_PATH} />`, `<Ticker types={SOURCE_TYPES} />`, `<System stores={STORES} rules={RULES} />`, `<BuildLog phases={PHASES} />`). Sections have ids `problem`, `pipeline`, `specimen`, `system`, `build-log` for nav anchors. Elements that Task 6 animates carry `data-anim` attributes: `hero-line`, `node`, `wire`, `problem-word`, `card`, `build-line`, `closing-type`.
- Copy: hero headline "Retrieval you can inspect."; hero figure label "FIG. 1 — QUERY PATH"; section labels "01 — Problem", "02 — Pipeline", "03 — Specimen", "04 — System", "05 — Build log"; closing "Ask it something."; buttons "Ask a question" (`/ask`) and "View on GitHub" (`GITHUB_URL`, `target="_blank" rel="noopener noreferrer"`).
- `Problem` splits its statement into one `<span data-anim="problem-word">` per word. `Ticker` renders the list twice for the loop, the second copy `aria-hidden`, and the CSS marquee stops under reduced motion and on hover.
- `app/page.tsx` renders Nav, Hero, Ticker, Problem, placeholders for Pipeline and Specimen (Task 5), System, BuildLog, Closing.

- [ ] **Step 1:** Write failing tests: `QueryDiagram` shows "planned" beside BM25 and Fuse + rerank and not beside Dense; `System` shows "planned" for OpenSearch and Redis and lists three rules; `BuildLog` shows four phases with exactly three "planned"; `Ticker` exposes each source type once to assistive technology.
- [ ] **Step 2:** Run `npx vitest run components/landing`. Expected: FAIL.
- [ ] **Step 3:** Implement the components, `landing.css` and the page.
- [ ] **Step 4:** Run `npm test && npm run lint`. Expected: PASS.
- [ ] **Step 5:** Commit `feat: add landing page sections`, push.

### Task 5: Pipeline and Specimen

**Files:**
- Create: `components/landing/Pipeline.tsx`, `components/landing/Specimen.tsx`, `components/landing/interactive.test.tsx`
- Modify: `app/page.tsx`, `app/landing.css`, `components/AnswerView.tsx` (export `SourceNote`)

**Interfaces:**
- Consumes: `INGESTION_STAGES`, `QUERY_STAGES`, `SAMPLE`; `splitAnswer` and `SourceNote` from `components/AnswerView`.
- Produces:
  - `<Pipeline ingestion={Stage[]} query={Stage[]} />`: client component. Each stage is a `<button aria-pressed>`; the active stage's note shows in a panel with `aria-live="polite"`. First ingestion stage is active initially. Exposes `data-anim="pipeline"` on its root and accepts stage changes from Task 6 through a `data-stage-index` attribute on each button. Under reduced motion or below 52rem, every stage's note renders in a plain list instead of the single panel.
  - `<Specimen sample={typeof SAMPLE} />`: client component. Shows the question, the answer with marker buttons (`aria-pressed`), and the selected passage through `SourceNote`. A visible label reads "Sample answer". No selection initially; a hint reads "Select a marker to read the passage it cites."

- [ ] **Step 1:** Write failing tests: Pipeline — clicking "Chunk" shows the chunk note and hides the connect note; pressing Enter on a focused stage selects it; "Rerank" carries "planned"; with reduced motion, every note is in the document. Specimen — clicking `[1]` shows citation 1's snippet, clicking again hides it; "Sample answer" is visible.
- [ ] **Step 2:** Run `npx vitest run components/landing/interactive.test.tsx`. Expected: FAIL.
- [ ] **Step 3:** Implement both components and wire them into the page.
- [ ] **Step 4:** Run `npm test && npm run lint`. Expected: PASS, including the existing `AnswerView` tests.
- [ ] **Step 5:** Commit `feat: add pipeline and specimen sections`, push.

### Task 6: Landing animation

**Files:**
- Create: `components/landing/LandingMotion.tsx`
- Modify: `app/page.tsx` (wrap in `SmoothScroll`, mount `LandingMotion`), `app/landing.css`, `components/landing/Nav.tsx`

**Interfaces:**
- Consumes: `data-anim` hooks from Tasks 4 and 5; `useReducedMotion`, `SmoothScroll`.
- Produces: `<LandingMotion />`, a client component that renders nothing and registers, inside one `useGSAP` with `gsap.matchMedia()`:
  - all widths, motion allowed: hero lines rise in (stagger 0.08s); diagram nodes fade in and wires scale from 0 on Y in sequence; problem words go from 0.2 opacity to 1 scrubbed across the section; cards stagger in on entry; build line scales on X to the last live phase; closing type scales from 0.8 on entry.
  - `(min-width: 52rem)` and motion allowed: the pipeline section pins for 10 stage-lengths of scroll and clicks through stages by index as progress advances.
  - reduced motion: registers nothing.
- Nav hides on scroll down and returns on scroll up with a CSS transform toggled by a `data-hidden` attribute. The closing button's cursor-follow uses `gsap.quickTo` on pointer move, desktop only.

- [ ] **Step 1:** Implement `LandingMotion` and the nav behaviour.
- [ ] **Step 2:** Run `npm test && npm run lint && npm run build`. Expected: PASS.
- [ ] **Step 3:** Run `npm run dev` and check `/` in a browser: each animation plays once in order, the pipeline pins and steps, nothing is left invisible, and no console errors appear. Check again with reduced motion emulated: no movement, all content visible.
- [ ] **Step 4:** Commit `feat: animate the landing page`, push.

### Task 7: Ask screen

**Files:**
- Modify: `components/AskForm.tsx`, `components/AnswerView.tsx`, `app/(app)/ask/page.tsx`, `app/globals.css`
- Create: `components/AskProgress.tsx`
- Test: `components/AskForm.test.tsx` (add one test)

**Interfaces:**
- Produces: `<AskProgress />` renders the existing status sentence "Searching your documents and checking citations…" plus an `aria-hidden` row of three labelled steps ("Retrieve", "Generate", "Verify") that advance on a CSS animation. `AskForm` renders it in place of the plain status paragraph. Button label becomes "Ask ↵" with accessible name "Ask" unchanged (the arrow is `aria-hidden`).
- Notices render in `.panel.notice`. The selected passage renders in `.panel.passage` with a signal-coloured left border and a CSS slide-in. `.source-path` and `.source-snippet` use `overflow-wrap: anywhere`.

- [ ] **Step 1:** Add a failing test: while a question is pending, the status sentence is in the document and the button is disabled.
- [ ] **Step 2:** Run `npx vitest run components/AskForm.test.tsx`. Expected: the new test fails only if the sentence moved; fix until every test in the file passes after the change.
- [ ] **Step 3:** Implement the restyle.
- [ ] **Step 4:** Run `npm test && npm run lint`. Expected: PASS with no change to existing assertions.
- [ ] **Step 5:** Commit `feat: restyle the Ask screen`, push.

### Task 8: Sources screen

**Files:**
- Modify: `app/(app)/sources/page.tsx`, `components/UploadForm.tsx`, `components/JobList.tsx`, `components/GithubSourceForm.tsx`, `app/globals.css`
- Test: `components/UploadForm.test.tsx`, `components/JobList.test.tsx` (add tests)

**Interfaces:**
- Produces: the page lays upload and GitHub panels in a two-column grid that stacks below 52rem. `UploadForm` wraps the existing file input in a drop zone: dropping files sets the same `files` state as choosing them, filtered to `.md`, `.pdf`, `.docx`; chosen file names list under the zone. `JobList` rows show a `<span class="job-bar" role="progressbar" aria-label="Job running">` for `running` and `pending` jobs only. Job errors and paths use `overflow-wrap: anywhere`.

- [ ] **Step 1:** Write failing tests: dropping `a.md` and `b.exe` on the zone lists only `a.md` and enables Upload; a `running` job renders a progressbar and a `succeeded` job doesn't.
- [ ] **Step 2:** Run `npx vitest run components/UploadForm.test.tsx components/JobList.test.tsx`. Expected: new tests FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `npm test && npm run lint`. Expected: PASS, including the Sources page tests.
- [ ] **Step 5:** Commit `feat: restyle the Sources screen`, push.

### Task 9: Verification and docs

**Files:**
- Modify: `README.md` (root) and `frontend/README.md`: describe the landing page and the `/ask` route.

- [ ] **Step 1:** Run `npm run lint && npm test && npm run build`. Expected: all pass.
- [ ] **Step 2:** With Postgres, Qdrant and the API running, check in a browser at 1440px and 375px, in light and dark: `/` (all sections, nav anchors, both buttons), `/ask` (ask a question, select a marker, see an outcome notice), `/sources` (upload a file, watch the job, see the GitHub form). Confirm no horizontal scroll at 375px and no console errors.
- [ ] **Step 3:** Tab through `/` by keyboard: every link and stage button is reachable with a visible focus outline.
- [ ] **Step 4:** Record what was checked and any defects fixed in the commit message body. Commit `docs: describe the redesigned frontend`, push.
