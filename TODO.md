# TODO

Improvement ideas for the pension calculator, roughly ordered by effort.

---

## Quick Fixes

- [ ] **`st.space("small")` crash** — Not a real Streamlit API; will throw AttributeError at runtime. Remove it.

---

## UX / Design Decisions

- [ ] **Move sidebar nudge to top** — The "← On the left sidebar" box currently sits after the two intro expanders. Move it to right below the opening paragraph so users see the prompt to fill inputs before reading the optional details.
- [ ] **Metrics: 3 × 2 layout + "Years Fund Covers" stat** — Currently a partial third row with an empty column. Reorganize as 2 rows of 3. Add "Years Fund Covers" (e.g. "18 / 30 years") as a sixth stat to give an at-a-glance answer on how long the personal fund lasts.
- [ ] **Feedback form backend** — Submissions are currently discarded (form shows success but saves nothing). Wire up to a real backend: write to a local `.jsonl` file for local use, or Google Sheets / Formspree for a deployed app.

---

## New Features

- [ ] **Vesting cliff** — Add a vesting year input. If the user leaves before vesting, pension value drops to zero or a partial amount. One of the strongest real-world arguments against pensions; currently not modeled.
- [ ] **Employer match** — Optional employer match for the personal fund. Would materially change results for many users.
- [ ] **Input presets** — A `st.selectbox` with named scenarios (e.g., "Teacher – CA", "Federal Employee", "Custom") that pre-fill sidebar inputs as starting points.
- [ ] **"What if" sensitivity panel** — Drag one variable (e.g., index returns) across a range and see a chart of outcomes, without manually re-running the calculator.
- [ ] **Monte Carlo / volatility simulation** — Toggle that runs N simulations with randomized annual returns (mean + standard deviation) and shows a distribution of outcomes. Directly addresses the constant-return limitation.

---

## Code Quality

- [ ] **Extract `compute_breakeven_rate()`** — The 25-line binary search block runs inline in the render path. Extract to a pure function to keep the render path as plain Streamlit calls and make the logic independently testable.
