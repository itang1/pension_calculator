"""Regression tests for the pure simulation core.

These run with no Streamlit context and no Google credentials — that is the
whole point of extracting simulation.py from the app (see AUDIT M-11). The two
scenarios mirror the in-app Case Study A and Case Study B copy.
"""

import pytest

import simulation as s

# --- Scenario fixtures (mirror the app's Case Study A and B) --------------------

CASE_A = dict(  # Personal fund wins
    starting_wage=120000, work_years=30, cola_increase=1.03, step_increase=1.055,
    promotion_years=(10, 20), promotion_increase=1.08, pension_contribution_rate=0.10,
    starting_allowance=70458, retirement_years=30,
)
CASE_B = dict(  # Pension wins
    starting_wage=65000, work_years=20, cola_increase=1.03, step_increase=1.055,
    promotion_years=(), promotion_increase=1.08, pension_contribution_rate=0.10,
    starting_allowance=27000, retirement_years=40,
)


def _run(case, index_returns_rate):
    return s.run_simulation(index_returns_rate=index_returns_rate, **case)


# --- salary_schedule -----------------------------------------------------------

def test_salary_schedule_year_one_is_half_step_average():
    sched = s.salary_schedule(100000, 5, 1.0, 1.10, (), 1.0)
    # step_increase is a multiplier (1.10). Year 1 averages Step 1 ($100,000)
    # and Step 2 ($110,000): 100000 * (1 + 1.10) / 2 = 105000.
    assert sched[0] == pytest.approx(105000.0)
    assert len(sched) == 5


def test_salary_schedule_is_single_source_of_truth():
    # The salary the deterministic sim uses in working year 1 must equal what
    # salary_schedule reports, guarding against the old triplicated logic drift.
    sched = s.salary_schedule(CASE_A["starting_wage"], CASE_A["work_years"],
                              CASE_A["cola_increase"], CASE_A["step_increase"],
                              CASE_A["promotion_years"], CASE_A["promotion_increase"])
    sim = _run(CASE_A, 1.07)
    assert sim["yearly_data"]["Salary"].iloc[0] == pytest.approx(sched[0])
    assert sim["yearly_data"]["Salary"].iloc[4] == pytest.approx(sched[4])


# --- Case Study A: personal fund wins ------------------------------------------

def test_case_a_personal_fund_wins():
    r = _run(CASE_A, 1.07)
    assert r["personal_balance"] > 0  # Option B survives with money to spare
    assert r["personal_fund_values"][CASE_A["work_years"]] == pytest.approx(1997570, rel=1e-3)
    assert r["personal_balance"] == pytest.approx(6072909, rel=1e-3)
    assert r["pension_redeemed_total"] == pytest.approx(3352069, rel=1e-3)
    assert r["pension_contribution_total"] == pytest.approx(769535, rel=1e-3)


# --- Case Study B: pension wins ------------------------------------------------

def test_case_b_pension_wins_and_fund_depletes():
    r = _run(CASE_B, 1.05)
    assert r["personal_balance"] < 0  # Option B runs dry
    pv = r["personal_fund_values"]
    depletion_year = next(
        (k for k in range(1, CASE_B["retirement_years"] + 1)
         if pv[CASE_B["work_years"] + k] <= 0),
        None,
    )
    assert depletion_year is not None
    assert depletion_year < CASE_B["retirement_years"]  # depletes before death


# --- Break-even -----------------------------------------------------------------

def test_breakeven_rate_leaves_fund_near_zero():
    args = (CASE_B["starting_wage"], CASE_B["work_years"], CASE_B["cola_increase"],
            CASE_B["step_increase"], CASE_B["promotion_years"], CASE_B["promotion_increase"],
            CASE_B["pension_contribution_rate"], CASE_B["starting_allowance"],
            CASE_B["retirement_years"])
    be = s.compute_breakeven_rate(*args)
    # At exactly the break-even return, the final balance should sit at ~$0.
    at_be = s.run_simulation(*args, 1.0 + be / 100.0)["personal_balance"]
    assert abs(at_be) < 5000  # within rounding of zero on a multi-million-dollar path


def test_breakeven_zero_when_fund_wins_at_flat_zero_percent():
    # A fund that survives even at 0% growth needs no positive break-even rate.
    strong = dict(CASE_A)
    strong["starting_allowance"] = 1000
    args = (strong["starting_wage"], strong["work_years"], strong["cola_increase"],
            strong["step_increase"], strong["promotion_years"], strong["promotion_increase"],
            strong["pension_contribution_rate"], strong["starting_allowance"],
            strong["retirement_years"])
    assert s.compute_breakeven_rate(*args) == 0.0


# --- Monte Carlo ----------------------------------------------------------------

def test_monte_carlo_zero_volatility_matches_deterministic():
    # With std=0 every path is identical and equals the flat-rate simulation,
    # so all percentile bands collapse onto the deterministic final balance.
    det = _run(CASE_A, 1.07)["personal_balance"]
    mc = s.run_monte_carlo(**CASE_A, mean_return=0.07, std_return=0.0, n_simulations=200)
    pcts = mc["percentiles"]
    assert pcts[0][-1] == pytest.approx(det, rel=1e-6)
    assert pcts[3][-1] == pytest.approx(det, rel=1e-6)


def test_monte_carlo_depletion_is_absorbing_no_negative_bands():
    mc = s.run_monte_carlo(**CASE_B, mean_return=0.05, std_return=0.15, n_simulations=1000)
    # Depleted paths are floored at $0, so no percentile band is ever negative.
    assert mc["percentiles"].min() >= 0.0
    # This is a pension-wins scenario, so most simulated futures run dry.
    assert 0.0 <= mc["depletion_prob"] <= 1.0
    assert mc["depletion_prob"] > 0.5


def test_monte_carlo_is_deterministic_for_fixed_seed():
    a = s.run_monte_carlo(**CASE_B, mean_return=0.05, std_return=0.15, n_simulations=500)
    b = s.run_monte_carlo(**CASE_B, mean_return=0.05, std_return=0.15, n_simulations=500)
    assert a["depletion_prob"] == b["depletion_prob"]


def test_monte_carlo_distribution_outputs_are_consistent():
    n = 400
    mc = s.run_monte_carlo(**CASE_B, mean_return=0.05, std_return=0.15, n_simulations=n)
    total_years = CASE_B["work_years"] + CASE_B["retirement_years"]

    assert mc["final_balances"].shape == (n,)
    assert mc["depletion_years"].shape == (n,)
    assert mc["median_path"].shape == (total_years + 1,)

    # Depletion is absorbing, so "has a depletion year" and "ended at $0" are
    # the same set of paths, and both must match the reported probability.
    assert (mc["depletion_years"] > 0).mean() == pytest.approx(mc["depletion_prob"])
    assert (mc["final_balances"] <= 0).mean() == pytest.approx(mc["depletion_prob"])

    # Depletion years fall inside the retirement window (0 = never ran out).
    assert mc["depletion_years"].min() >= 0
    assert mc["depletion_years"].max() <= CASE_B["retirement_years"]

    # The median path sits inside the 25th-75th percentile band everywhere.
    pcts = mc["percentiles"]
    assert (mc["median_path"] >= pcts[1] - 1e-9).all()
    assert (mc["median_path"] <= pcts[2] + 1e-9).all()


def test_monte_carlo_zero_volatility_distribution_matches_deterministic():
    det = _run(CASE_A, 1.07)["personal_balance"]
    mc = s.run_monte_carlo(**CASE_A, mean_return=0.07, std_return=0.0, n_simulations=100)
    # Every path is the flat-rate path: same final balance, nobody runs out.
    assert mc["median_path"][-1] == pytest.approx(det, rel=1e-6)
    assert mc["final_balances"][0] == pytest.approx(det, rel=1e-6)
    assert (mc["depletion_years"] == 0).all()
