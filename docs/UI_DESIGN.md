# AskMyCity UI redesign — design spec

Target: dark, modern, professional feel; onboarding context for a visitor who's
never heard of "311"; three clickable example questions that ask themselves;
the existing "How I got this" transparency panel kept, restyled to match.

Everything below is buildable with Streamlit's theme config + `unsafe_allow_html`
CSS injection + native widgets (`st.button`, `st.columns`, `st.expander`,
`st.container`). No custom components, no JS, no animation beyond CSS
transitions on hover/focus (which Streamlit's injected `<style>` supports fine).

## 1. Color palette

Set as `.streamlit/config.toml` theme tokens (Streamlit maps these to CSS vars
`--background-color`, `--primary-color`, etc., so custom CSS can reference
`var(--primary-color)` instead of hardcoding hex — keeps the two in sync).

| Token | Hex | Use |
|---|---|---|
| `backgroundColor` | `#0B0F14` | App background — near-black, slight blue cast |
| `secondaryBackgroundColor` | `#131A22` | Cards, input fields, expander body |
| Border / divider (CSS only) | `#232D38` | Card borders, hr, expander border |
| `primaryColor` | `#38BDF8` | Buttons, links, focus ring, active states (sky blue) |
| Accent hover (CSS only) | `#0EA5E9` | Button/chip hover + pressed state |
| `textColor` | `#E6EDF3` | Body text, headings |
| Muted text (CSS only) | `#9AA7B2` | Captions, tagline, helper text |
| Data highlight (CSS only, optional) | `#34D399` | Emphasized numbers in answers (stretch, see §7) |

Keep Streamlit's default semantic colors for `st.error`/`st.warning`/`st.info` —
don't override those; they already read fine on a dark background and changing
them risks breaking contrast.

`.streamlit/config.toml`:
```toml
[theme]
base = "dark"
backgroundColor = "#0B0F14"
secondaryBackgroundColor = "#131A22"
primaryColor = "#38BDF8"
textColor = "#E6EDF3"
font = "sans serif"
```

## 2. Typography

- **UI font:** Inter, loaded via Google Fonts `@import` in the injected CSS
  (`font` in config.toml only picks Streamlit's built-in generic stacks, so
  Inter needs the CSS import to actually apply). Fallback stack:
  `"Inter", -apple-system, "Segoe UI", sans-serif`.
- **Monospace (tool-call JSON in the transparency panel):** leave Streamlit's
  default monospace stack — it's already fine, don't fight it.
- Sizes/weights:
  - App title (`AskMyCity`): 1.9rem, weight 700, letter-spacing -0.02em.
  - Tagline / explainer body: 0.95rem, weight 400, color = muted text.
  - Section labels ("Try asking:", "Ask a question"): 0.8rem, weight 600,
    uppercase, letter-spacing 0.04em, color = muted text — gives the page
    visual structure without adding more `st.header` chrome.
  - Answer text: default body size (Streamlit default, ~1rem), weight 400.

## 3. Layout, section by section

Page config stays `layout="centered"`; bump the effective content width
slightly via CSS (`.block-container { max-width: 760px; }`) since the current
centered column reads a little narrow for a chart-bearing app.

### 3.1 Header
- Emoji/icon + "AskMyCity" title on one line (unchanged concept, restyled).
- Tagline directly under it, muted-text style, one line: keep the existing
  factual line about the tool-use agent — it's good technical credibility for
  a portfolio piece, don't cut it:
  > *Ask plain-English questions about Austin's 311 data. An LLM agent turns
  > your question into calls to a small set of deterministic analytics tools —
  > no arbitrary code execution.*
- Thin bottom border (`1px solid #232D38`) with `padding-bottom` to separate
  header from the explainer card below.

### 3.2 "What is Austin 311?" explainer card
New section — this is the onboarding context the brief asks for. Rendered as
a bordered card (`div` with secondary-background fill, `1px solid #232D38`,
`border-radius: 10px`, padding ~16px) directly under the header, always
visible (not an expander — a first-time visitor shouldn't have to click to
get oriented).

Exact copy:

> **What's Austin 311?**
> 311 is the non-emergency line (and app) Austin residents use to report
> stuff like potholes, missed trash pickup, graffiti, or a stray dog — anything
> that needs the city's attention but isn't a 911 emergency. Every request
> becomes a public record: what was reported, where, when, and how long it
> took to resolve. This app lets you ask questions about that record in plain
> English instead of writing SQL. The dataset here covers **Sept 2025 – Aug
> 2026**.

Keep it to that length — one card, no sub-bullets. A visitor should be able to
read it in ~5 seconds and move to the input.

### 3.3 Example questions ("Try asking:")
Section label "TRY ASKING:" (styled per §2), then **3 chip-style buttons in a
row** via `st.columns(3)`, one `st.button` per column, full-width within its
column.

Chip styling (CSS on `.stButton > button`, scoped to this row via a wrapper
`div` + attribute or a dedicated CSS class — see §6 for the selector
approach): pill shape (`border-radius: 999px`), transparent background,
`1px solid #232D38` border, muted text color at rest; on hover, border and
text switch to accent (`#38BDF8`), background gets a faint accent tint
(`rgba(56, 189, 248, 0.08)`). This visually distinguishes them from the
primary "Ask" button (solid accent fill) so it's clear chips are *suggestions*
and "Ask" is *submit*.

The three questions (pulled from `data/eval_questions.md`, one per answer
type so the demo shows range):

1. **"How many 311 requests were filed in total?"** — *count*
2. **"What are the top 10 most common request types?"** — *ranked-list*
3. **"How many requests per month were filed over the year?"** — *trend*

Order matters: simplest/broadest question first (total count), then a
ranked-list (visually a bar chart), then a trend (line chart) — so a visitor
scanning left to right sees increasing sophistication and, if they click all
three in order, sees both chart types.

### 3.4 Ask box
- `st.text_input` restyled: rounded corners (`border-radius: 8px`),
  `#131A22` fill, `#232D38` border at rest, accent-colored border + subtle
  glow (`box-shadow: 0 0 0 3px rgba(56,189,248,0.15)`) on focus.
- "Ask" button: primary/filled style (Streamlit's default `type="primary"`
  already picks up `primaryColor`, so this needs no extra CSS beyond
  rounding to match the input — `border-radius: 8px`).
- Placeholder text unchanged: *"e.g. What were the top 5 complaint categories
  last month?"*

### 3.5 Answer area
Unchanged structurally (markdown answer text, then the existing
line/bar/dataframe chart logic) — just inherits the dark theme automatically
once `config.toml` sets `base = "dark"` (Streamlit's own chart theming and
Altair's `st.altair_chart` follow the app theme). No spec changes needed here
beyond confirming the bar chart's color reads fine on dark — Altair's default
blue mark works on `#0B0F14`; if it looks flat, swap the mark color to the
accent (`#38BDF8`) via `.mark_bar(color="#38BDF8")` in `streamlit_app.py`
(one-line change, flag for developer).

### 3.6 "How I got this" transparency panel — kept, restyled
Keep `st.expander("How I got this")` exactly where it is today (right after
the answer/chart). Restyle only the container: the expander's border and
background should match the explainer card in §3.2 (same `#232D38` border,
`#131A22` fill, `border-radius: 10px`) so it reads as the same "card" visual
language rather than Streamlit's default expander chrome. Inside, keep the
existing structure (tool name in bold-mono, `st.json(call.input)`,
error/caption for the result) — no content changes, this is purely a skin.

### 3.7 Footer
Small, muted, single line at the very bottom, below everything:
> *Built with an LLM tool-use agent over real Austin 311 open data · [GitHub]*

Muted text color, 0.75rem, centered, `padding-top: 2rem`. Optional — cut if
the developer feels it's clutter, but it's a normal portfolio-piece touch.

## 4. Example-question button behavior

Click → fills the question **and** submits it immediately (no second click),
per the brief. Implementation shape (for the developer, not exact code):

1. Keep a `st.session_state["question"]` string (default `""`) and use it as
   the `text_input`'s `value=` so it can be programmatically set.
2. Each example button's `on_click` callback sets
   `st.session_state["question"] = "<that question text>"` and a flag like
   `st.session_state["auto_submit"] = True`.
3. On rerun, treat `submitted = st.button("Ask", ...) or st.session_state.pop("auto_submit", False)`
   as the trigger for calling `ask()` — i.e. an example click satisfies the
   same "run the query" branch a manual Ask-button click does, without
   requiring the user to press Ask afterward.
4. The text input should visibly show the clicked question (not just run it
   silently) — so the user sees what was asked, matching how the manual flow
   looks after typing + Ask.

This needs no new Streamlit APIs — `st.button(on_click=...)` + session state +
Streamlit's automatic rerun-on-widget-interaction covers it.

## 5. Empty / loading / error states

- **Loading:** keep `st.spinner("Thinking...")`; no change needed, it already
  themes with the page.
- **No API key / dataset not ready:** keep existing `st.warning`/`st.info` +
  `st.stop()` — those Streamlit semantic colors already work on dark, don't
  restyle.
- **Error from `ask()`:** keep existing `st.error(...)`. No change.

## 6. CSS injection approach (for the developer)

One `st.markdown(<style>...</style>, unsafe_allow_html=True)` block near the
top of `main()`, containing:
- The Inter `@import` (or `<link>` — either works; `@import` inside the
  injected `<style>` is simplest).
- Rules keyed off Streamlit's existing stable-ish structural classes/attributes
  (`.block-container`, `.stTextInput input`, `.stButton > button`,
  `.stExpander`, `div[data-testid="stExpander"]`) rather than nth-child
  guessing, since Streamlit's DOM shifts between versions.
- To differentiate the 3 chip buttons from the primary "Ask" button (both are
  `st.button`), wrap the chip row in a `st.container()` and give that
  container a marker (e.g. a preceding zero-height `<div id="example-chips">`
  hack, or simplest: rely on `type="secondary"` vs `type="primary"` — Streamlit
  buttons already support `type="secondary"`, which is the *simpler* path
  here: make the chips `st.button(..., type="secondary")` and style
  `button[kind="secondary"]` for the pill look, leaving `button[kind="primary"]`
  (the Ask button) alone. Prefer this over DOM-marker hacks.

## 7. Stretch ideas (optional, flag to team lead — not required for v1)

- `st.metric` for pure-count answers (e.g. the "total requests" question)
  showing the number large or with the `#34D399` highlight color, instead of
  only prose — nice for count-type questions but needs `agent.py`'s answer
  object to expose "this is a scalar" separately from the chart table, which
  is a small backend change beyond pure UI/CSS. Not needed for the redesign
  to land.
- Small colored "count / trend / ranked-list" tag under each example chip —
  cute but adds visual noise for a 3-button row; skip unless the mockup review
  says otherwise.

## 8. Files this touches

- `.streamlit/config.toml` — new file, theme tokens from §1.
- `app/streamlit_app.py` — CSS injection block, explainer card, example-chip
  row + session-state wiring, expander restyle (all additive; no changes to
  `ask()`/tool logic).
