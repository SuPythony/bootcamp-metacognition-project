# Frontend Redesign Plan — Loom

> **Status**: planning. No code changes yet. Decisions below are locked; per-PR scoping is suggested order, not contract.
>
> **Scope**: pure visual + interaction layer of `frontend/`. No backend contract changes. No core-logic edits. Mock mode (`VITE_USE_MOCK=true`) must continue to work end-to-end at every step.

---

## Locked Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Identity track: Editorial Lab** (cream paper, serif display + sans body, ink accents, hand-drawn dividers) | Best fit for "your thinking, made visible." Differentiates from every AI chat clone. Makes ThinkingTrace feel like a keepsake artifact, not a dashboard. |
| 2 | **Placeholder product name: Loom** | Weaves thoughts together. Short, neutral, easy to swap. A logo slot is wired in the top-left of every chrome surface so a future mark just drops in. |
| 3 | **Motion: `framer-motion`** | ~12kb gz, declarative, plays nicely with React 18, supports `prefers-reduced-motion` out of the box. CSS-only would punish the timeline + tree animations. |
| 4 | **Dark mode in v1** | Affects token shape from day one. Tailwind `darkMode: "class"`, toggle stored in `localStorage`, default = system preference. |

Cross-cutting rules these decisions imply:

- Every color must be a token, never a raw Tailwind palette name in a component. The single source of truth lives in `tailwind.config.js` (light) + a `.dark` variant.
- Every font size in chrome (headlines, labels, captions) maps to a named scale (`display`, `serif-lede`, `body`, `caption`, `mono`). No ad-hoc `text-[13px]` after Phase 1.
- Motion is meaning: state change, achievement, transition. Never decoration. Respect `prefers-reduced-motion`.
- Anything that calls itself "AI" anywhere in the UI gets reframed. We do not say "AI tutor"; we say "tutor" or "Loom."

---

## Brand & Identity

### Name: Loom (placeholder)

Tagline candidate: *"Your thinking, traced."*

### Logo slot

- Reserved 28×28 area in the top-left of every chrome surface (`OnboardingView`, `SessionView` header, `WrapUpView`).
- v1 = monogram glyph in display serif, ink fill. Component: `<Brandmark />`. Single source — swap once when real mark lands.
- Word-mark (`Loom` in display serif) sits to the right of the glyph on `OnboardingView` and `WrapUpView`; on `SessionView` header only the glyph is shown (tight chrome).

### Palette (light → dark)

| Token | Light | Dark | Use |
|---|---|---|---|
| `paper` | `#FBF8F2` (cream) | `#14130F` (ink-black) | Page bg |
| `surface` | `#FFFFFF` | `#1C1B17` | Card bg, raised |
| `surface-muted` | `#F2EDE2` | `#26241F` | Subtle card bg |
| `ink` | `#1A1A1A` | `#EDEAE0` | Primary text |
| `ink-soft` | `#4A4742` | `#B8B3A6` | Secondary text |
| `ink-faint` | `#8B857A` | `#6E6A60` | Tertiary text, labels |
| `rule` | `#E5DFD0` | `#2F2C25` | Dividers, borders |
| `accent` | `#6B2D5C` (plum) | `#C57BB1` (soft plum) | Primary action, brand |
| `accent-soft` | `#F4E8EF` | `#3A1F33` | Accent bg, highlights |
| `solved` | `#5C7A52` (sage) | `#A6C39A` | Solved subproblem |
| `hint` | `#A86B1F` (ochre) | `#E0B26F` | Hint badge, escape hatch |
| `calibrate` | `#3F5B7A` (slate-blue) | `#8FB0D1` | Calibration widget |
| `alarm` | `#A33C2A` (terracotta) | `#E08471` | Errors |

Selection states are derived (`accent` + 8% alpha for hover, `accent` + 16% for active). Documented in `tokens.css`.

### Type

| Scale | Family | Use |
|---|---|---|
| `display` | Fraunces 600 | Page headlines, ThinkingTrace hero |
| `serif-lede` | Fraunces 400 italic | Pull quotes (initial / final understanding) |
| `body` | Inter 400 | Chat, body copy |
| `body-emphasis` | Inter 500 | Buttons, important inline |
| `label` | Inter 500, uppercase, tracking-wide | Section labels |
| `caption` | Inter 400 | Stat captions, hint text |
| `mono` | JetBrains Mono | Subproblem IDs, code, exit codes |

Both Fraunces and JetBrains Mono via `@fontsource-variable/*` (self-hosted, no CDN). Inter is already system-acceptable; ship Inter via Fontsource too for consistency.

### Shape language

- Cards: `rounded-lg` (8px) for utility, `rounded-md` (6px) for buttons, `rounded-xl` reserved for ThinkingTrace hero only.
- Borders: `1px solid token(rule)`. Shadows used sparingly — only on modal + ToolPane slide-in.
- Dividers in long content: hand-drawn SVG horizontal rule (single component, swappable later for a richer ornament).

---

## Phase 0 — Pre-work (one PR before Phase 1)

Foundations that touch everything. Cheap to land first.

- Add deps: `framer-motion`, `@fontsource-variable/fraunces`, `@fontsource-variable/inter`, `@fontsource-variable/jetbrains-mono`, `lucide-react` (icons).
- `tailwind.config.js`:
  - `darkMode: "class"`
  - Extend `colors` with tokens above (both light + dark mode wired via CSS variables so dark mode is one class flip).
  - Extend `fontFamily` with `display`, `body`, `mono`.
  - Extend `borderRadius` if needed.
- `frontend/src/styles/tokens.css`: CSS variable declarations for `:root` and `.dark`, focus ring token, transition timing token (`--ease-soft: cubic-bezier(0.22, 1, 0.36, 1)`).
- `frontend/src/styles/index.css`: import token CSS + font CSS, set `<body>` defaults.
- `frontend/src/components/brand/Brandmark.tsx`: single source for glyph + optional wordmark prop.
- `frontend/src/components/theme/ThemeProvider.tsx`: reads system preference, supports manual override via context, persists to `localStorage`. Mount in `main.tsx`.
- `frontend/src/components/theme/ThemeToggle.tsx`: small sun/moon icon button. Used in chrome.

No other component touched. App still looks like today after this PR — but every subsequent PR can pull tokens.

---

## Phase 1 — Foundation Restyle (palette, type swap across existing surfaces)

**Goal**: kill the generic-Tailwind look. No new components, no new layouts — just retoken every existing component.

Touched files:
- `OnboardingView.tsx` — drop `bg-gradient-to-br from-indigo-50`; use `bg-paper` + paper texture (subtle noise PNG, optional). Headline in `display` font. Form rule-lines instead of full borders. CTA uses `accent`.
- `SessionView.tsx` — chrome bg → `paper`. Header rule below. Domain label = `mono`, phase label = `caption` (will be replaced in Phase 2).
- `WrapUpView.tsx` — drop gradient; serif headline.
- `ChatPane.tsx` — bubbles retokened (kept for now; full redesign in Phase 5).
- `SubproblemPanel.tsx`, `ToolPane.tsx`, `ThinkingTraceDrawer.tsx` — borders + bgs retokened.
- `HintBadge.tsx`, `CalibrationCheck.tsx`, `ReflectionPrompt.tsx`, `ConfidenceWidget.tsx` — retokened.
- All specialization components (`AlgebraSteps`, `GraphView`, `RuleRecallPrompt`, `CodeOutput`, `PseudocodePad`, `OutlineTree`, `DataTable`) — at minimum retokened; full redesign in Phase 7.

Acceptance: every screen renders in light + dark mode with no raw indigo/gray Tailwind names left in any component.

---

## Phase 2 — Phase Stepper (always-visible journey)

**Goal**: replace text-chip phase label with a persistent visual stepper. Anchors the learning journey, makes progress legible without reading.

- New `frontend/src/components/PhaseStepper.tsx`:
  - 4 nodes: clarification → decomposition → solving → wrap_up.
  - States per node: `pending` (ring outline), `active` (filled accent, subtle pulse via framer-motion), `done` (filled `ink-soft`, check glyph inside).
  - Thin rule connectors between nodes.
  - Compact horizontal mode (for header) + vertical mode (reserved for future mobile).
- Mounted in `SessionView` header where the current phase chip lives.
- Animates filled-state transitions on phase change.
- Tooltips on hover with phase descriptions.

---

## Phase 3 — Hero Surface: ThinkingTraceDrawer Redesign

**Goal**: turn the dashboard into a narrative artifact a student wants to screenshot and keep. This is the demo-pitch surface.

Layout sections (top → bottom):

1. **Title block** — `Brandmark` + `Your thinking, traced` in `display`. Subtitle = ISO date + domain. Hand-drawn rule below.
2. **Understanding shift** — two-quote diptych. Left card: "I started thinking…" with `initial_understanding` in `serif-lede` italic. Right card: "I ended up here." with `final_understanding` in `body-emphasis`. SVG connector line between (animates on mount). Delta label as a small chip on the connector.
3. **Process timeline** — vertical timeline. Events: subproblem solved, hint requested, self-correction, calibration check, escape hatch. Each event = small chip with icon (`lucide-react`) + one-line caption + `mono` timestamp. Self-corrections get an extra glow (sage accent).
4. **Calibration plot** — small horizontal predicted-vs-outcome plot. One-sentence narration below (`evidence` field). Replaces the existing "X/5" stat treatment for confidence.
5. **By the numbers** — turns, hints used, self-corrections, in editorial style: large `display` numbers with `caption` labels under each. Not stat cards.
6. **Closing line** — auto-generated `body-emphasis` sentence. E.g. *"On 2026-05-16, you decomposed 3 parts and changed your mind twice."*

Component split:
- `frontend/src/components/trace/TraceHero.tsx` — sections 1–2.
- `frontend/src/components/trace/TraceTimeline.tsx` — section 3.
- `frontend/src/components/trace/CalibrationPlot.tsx` — section 4.
- `frontend/src/components/trace/TraceNumbers.tsx` — section 5.
- `frontend/src/components/trace/TraceFooter.tsx` — section 6.
- `ThinkingTraceDrawer.tsx` becomes a thin composer.

Motion: each section fades + rises into view on scroll (`useInView` from framer-motion). Diptych connector line draws itself on mount.

---

## Phase 4 — SubproblemPanel: Decomposition Tree

**Goal**: flat list → branching tree. Makes decomposition feel like building, not a checklist.

- SVG connector lines between subproblem cards (vertical spine + horizontal branches).
- Active card scaled +2%, sage glow border.
- Status glyphs: `pending` (○), `active` (◐ pulsing), `solved` (●).
- Empty state (before first decomposition): sketch placeholder + copy *"Your breakdown will grow here."*
- Insert animation: card fades in + slides from the connector point.
- HintBadge moves to a small ribbon corner of the card instead of inline.

---

## Phase 5 — ChatPane: Dialogue, not Messenger

**Goal**: less iMessage, more transcript / journal. The "AI chat" feel is what makes everything else look generic.

- Drop the gray bubble for assistant messages. Replace with: thin `rule` left border + small `Tutor` label in `label` style + `ink` body text. Reads like a transcript.
- Keep user side emphasized: filled `accent-soft` bubble with `ink` text, `rounded-md`. *Your* contribution stands out, which matches the product thesis.
- `Thinking…` italic → three breathing dots animation (framer-motion `<motion.span>` looped opacity).
- Input bar: replace full border on textarea with bottom rule only. Send button = icon button + keyboard hint `↵`.
- Inline directives below assistant messages get more breathing room (one rule of separation, not direct stacking).

---

## Phase 6 — Inline Widget Identity

**Goal**: `CalibrationCheck`, `ReflectionPrompt`, `RuleRecallPrompt` are metacognitive moments. They should feel earned, not utility.

- Each gets a left ribbon stripe + tiny `lucide-react` icon (compass for calibration, mirror/eye for reflection, scales for rule recall).
- Question text in `serif-lede` for weight; buttons in `body-emphasis`.
- Entrance: soft fade + 8px rise.
- `CalibrationCheck`: replace the 5-button row with a horizontal slider/segmented control. Endpoints labeled ("Not sure" ↔ "Very confident"). Selection animates a small marker.
- `ReflectionPrompt`: thicker visual weight (slightly larger padding, deeper rule). After-submit confirmation: "Got it — saved to your trace."
- All three respect the `placement` contract: inline (in chat), side_panel (in ToolPane), modal (overlay).

---

## Phase 7 — Specialization Stubs (full design pass)

Each domain component must visually match the system. No bare HTML left.

- **`programming/CodeOutput.tsx`** — terminal aesthetic. `mono` font, dark surface even in light mode (always-dark to read like a real terminal), prompt sigil, color-split stdout/stderr, exit code chip. Copy button.
- **`programming/PseudocodePad.tsx`** — notebook-paper bg, ruled horizontal lines, `mono` textarea. Prompt label in `serif-lede`.
- **`essay/OutlineTree.tsx`** — indented tree with claim/evidence two-tone. Expand/collapse per node. Tree connector lines (matches Phase 4 style).
- **`science/DataTable.tsx`** — proper editorial table: zebra rows, sticky header, mono numbers, serif headers.
- **`science/GraphView.tsx`** + **`math/GraphView.tsx`** — frame + caption + axis label slot. Image embed gets a thin rule + caption in `caption` style.

---

## Phase 8 — Onboarding: Invitation, not Form

**Goal**: kill the "sign up" feel. First impression sets the editorial tone.

- Full-bleed `paper` bg. Single centered column, generous vertical space.
- `Brandmark` top, wordmark.
- Display headline: *"What're you working on today?"*
- Username = small input below the headline (`label`: "call me…"). No card, just a baseline rule.
- Problem = large textarea, ruled-paper styling (faint horizontal lines), `body` text.
- One CTA, full-width, `accent` fill.
- No "no account needed" disclaimer — short form makes it self-evident.
- `ThemeToggle` in the top-right.

---

## Phase 9 — Loading, Empty, Error States

- ThinkingTrace load: skeleton placeholders matching the section layout (not a "Loading…" string).
- ChatPane Thinking dots already in Phase 5.
- SubproblemPanel empty state already in Phase 4.
- Shared `<ErrorCard />` component: paper card + sketch icon + message + retry button. Used by `ErrorBoundary` and inline error states.
- Network-down state in `OnboardingView`: replace `"Could not connect. Is the backend running?"` with the new ErrorCard.

---

## Phase 10 — Motion + Micro-interactions

Targets (all via framer-motion):

- Subproblem card insert + status-change.
- Phase stepper transition.
- ThinkingTrace section reveal on scroll.
- Inline widget entrance.
- Modal directive backdrop fade.
- Theme toggle sun↔moon cross-fade.
- Send-button press feedback.
- Breathing dots.

Rules:
- `prefers-reduced-motion: reduce` honored globally via a `<MotionConfig reducedMotion="user">` wrapper in `main.tsx`.
- No spring durations > 400ms.
- No motion that delays interaction (e.g. modal must be dismissible during enter animation).

---

## Phase 11 — Accessibility + Polish

- Focus rings: visible, `accent` color, 2px offset. Defined once in `tokens.css`.
- `aria-label` on every icon button (`ThemeToggle`, send, dismiss, copy, etc.).
- Keyboard nav: tab through subproblem cards, arrow keys on calibration segmented control, `Esc` dismisses modal directives.
- Color contrast audit: every text-on-bg pair ≥ 4.5:1 (use the WebAIM contrast checker; document any caption-grade exception ≥ 3:1).
- `prefers-reduced-motion` honored (covered in Phase 10).
- Skip-to-content link in `SessionView` (chat area).
- Theme toggle exposes `aria-pressed`.

---

## Suggested PR Sequencing

| PR | Scope | Why this order |
|---|---|---|
| 0 | Phase 0 — deps, tokens, theme provider, Brandmark | Foundations. Doesn't change look. |
| 1 | Phase 1 — retokenize existing components | Biggest visible jump per LOC. Whole app suddenly looks intentional. |
| 2 | Phase 2 — PhaseStepper | Standalone surface, small blast radius. |
| 3 | Phase 3 — ThinkingTrace redesign | Demo-pitch surface; ship before deploy. |
| 4 | Phase 5 + Phase 6 — Chat dialogue + widget identity | Both touch ChatPane; bundle. |
| 5 | Phase 4 — Subproblem tree | Standalone; can run in parallel with PR 4. |
| 6 | Phase 7 — specialization stubs | Parallel-friendly per domain. |
| 7 | Phase 8 + Phase 9 — Onboarding + states | Smaller surfaces, ship together. |
| 8 | Phase 10 + Phase 11 — motion + a11y | Polish last, after surfaces are stable. |

---

## Out of Scope

- New API contract fields or backend changes.
- Mobile-first layout (responsive enough not to break is the v1 bar; phones can wait).
- Real product name + final logo mark.
- Critique Mode UI (deferred to v1.1 per CLAUDE.md).
- Sound, haptics, illustrations beyond simple sketch dividers.

---

## Open Items to Revisit After Phase 3

- Whether the `display` serif (Fraunces) reads well at small sizes in dark mode — may need to swap for Spectral.
- Whether `framer-motion` bundle size is acceptable post-tree-shake; if not, fall back to `motion/react` (lighter API-compatible build).
- Whether to add a one-line empty-session pitch on `OnboardingView` ("Bring a problem. Loom won't solve it for you — it'll help you solve it yourself.") or keep the page silent.
