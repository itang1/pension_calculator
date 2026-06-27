# TODO

Improvement ideas for the pension calculator.

---

- [ ] Review the rest of the page from Simulation Results downwards

## UX / Interactivity

- [ ] **Input validation feedback** — If promotion years fall outside `[1, work_years]` or can't be parsed, show a clear `st.error()` message rather than silently ignoring bad input.
- [ ] **"Fund runs out in year X" stat** — When the personal fund goes negative, compute and surface exactly which retirement year it's depleted, not just the final negative balance.
- [ ] **"Break-even return rate"** — Calculate and display the minimum index return rate at which the personal fund would survive all retirement years, so users can immediately see what market performance they need.
- [ ] **Break-even annotation on the chart** — Automatically mark the year the personal fund first hits zero on the chart itself.
- [ ] **Input presets / templates** — A `st.selectbox` with named scenarios (e.g., "Teacher – CA", "Federal Employee", "Custom") that pre-fill the sidebar inputs as starting points.
- [ ] **"What if" sensitivity analysis** — A section where dragging one variable (e.g., index returns) across a range produces a chart of outcomes, without re-running the full calculator manually.
- [] Ask users for feedback, make a feedback submission form, give them list of things to look out for


---

## Calculation / Modeling

- [ ] **Vesting cliff** — Add a vesting year input. If the user leaves before vesting, pension value drops to zero (or a partial amount). This is one of the strongest arguments against pensions and is currently not modeled.
- [ ] **Employer match** — Add an optional employer match field for the personal fund. Listed as a known omission; would materially change results for many users.
- [ ] **Monte Carlo / volatility simulation** — Optional toggle that runs N simulations with randomized annual returns (mean + standard deviation) and shows a distribution of outcomes rather than one deterministic line. Directly addresses the "no market volatility" limitation.

---

## Code Quality

- [ ] **Refactor simulation into a pure function** — The calculation loop runs directly in the render path. Extracting it to `calculate_scenario(params) -> results` makes it testable, cacheable with `@st.cache_data`, and reusable for Monte Carlo and sensitivity analysis.
- [ ] **Fix Year 1 step-increase formula** — `salary * (1 + step_increase) / 2` is incorrect when `step_increase` is already a multiplier (e.g., `1.055`). The correct average of the two steps is `salary * (1 + step_increase) / 2` only when `step_increase` is a rate. Since the variable is stored as a multiplier, the formula should be `(salary + salary * step_increase) / 2`.
- [ ] **Replace bare `except:`** — Promotion year parsing uses `except:` which swallows all errors silently. Change to `except ValueError:`.
- [ ] **Avoid `pd.concat` inside a loop** — Appending rows one at a time is slow. Build a list of dicts and call `pd.DataFrame(rows)` once after both loops.
