# TODO

Improvement ideas for the pension calculator, roughly ordered by effort.

---

## UX / Design Decisions

- [ ] **Feedback form backend** — Submissions are currently discarded (form shows success but saves nothing). Wire up to a real backend: write to a local `.jsonl` file for local use, or Google Sheets / Formspree for a deployed app.

---

## New Features

- [ ] **Vesting cliff** — Add a vesting year input. If the user leaves before vesting, pension value drops to zero or a partial amount. One of the strongest real-world arguments against pensions; currently not modeled.
- [ ] **Employer match** — Optional employer match for the personal fund. Would materially change results for many users.
- [ ] **Input presets** — A `st.selectbox` with named scenarios (e.g., "Teacher – CA", "Federal Employee", "Custom") that pre-fill sidebar inputs as starting points.
- [ ] **"What if" sensitivity panel** — Drag one variable (e.g., index returns) across a range and see a chart of outcomes, without manually re-running the calculator.
- [ ] **Monte Carlo / volatility simulation** — Toggle that runs N simulations with randomized annual returns (mean + standard deviation) and shows a distribution of outcomes. Directly addresses the constant-return limitation.

