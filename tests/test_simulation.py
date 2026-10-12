"""Regression tests for the pure simulation core.

These run with no Streamlit context and no Google credentials; that is the
whole point of extracting simulation.py from the app (see AUDIT M-11). The two
fixtures are fixed engine regressions; the in-app case studies themselves are
checked against their copy in tests/test_case_studies.py.
"""

import math

import numpy as np

import pytest

import simulation as s

# --- Scenario fixtures ----------------------------------------------------------

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


# --- Step schedule ----------------------------------------------------------------

def test_step_count_and_midyear_flag():
    # Two step raises, no mid-year averaging: raises land in years 2 and 3 only.
    sched = s.salary_schedule(100000, 5, 1.0, 1.10, (), 1.0, step_count=2,
                              first_step_midyear=False)
    assert sched == pytest.approx([100000, 110000, 121000, 121000, 121000])
    # No step raises at all means no year-1 averaging either.
    flat = s.salary_schedule(100000, 3, 1.0, 1.10, (), 1.0, step_count=0)
    assert flat == pytest.approx([100000, 100000, 100000])


# --- Built-in plan rules ------------------------------------------------------------

@pytest.mark.parametrize("years,age,factor,reduction,status", [
    (30, 55, 2.0, 1.0, "immediate"),     # 55 with 30 years: unreduced
    (30, 52, 2.0, 0.835, "immediate"),   # under 55 with 30 years: reduced
    (30, 63, 2.1, 1.0, "immediate"),
    (20, 60, 1.5, 1.0, "immediate"),
    (20, 63, 2.0, 1.0, "immediate"),
    (20, 55, 1.5, 1.0, "deferred"),      # can't retire before 60 without 30 years
    (4, 65, 0.0, 1.0, "unvested"),
])
def test_plan_benefit_rules(years, age, factor, reduction, status):
    b = s.plan_benefit(years, age, 100000)
    assert b["status"] == status
    assert b["factor_pct"] == factor
    assert b["reduction"] == pytest.approx(reduction)


def test_plan_benefit_cap_and_deferral():
    capped = s.plan_benefit(45, 66, 100000)  # 45 x 2.1% = 94.5%, capped at 80%
    assert capped["capped"] and capped["allowance"] == pytest.approx(80000)
    deferred = s.plan_benefit(20, 55, 100000)
    assert deferred["deferral_years"] == 5 and not deferred["cola_applies"]
    assert deferred["allowance"] == pytest.approx(30000)


def test_early_reduction_table():
    # Spot values from the plan's published table.
    for age, factor in [(48, .7150), (54, .8950), (55, .9250), (56, .9400), (59, .9850), (60, 1.0)]:
        assert s.early_reduction_factor(age) == pytest.approx(factor)


def test_deferred_payouts_and_separate_retiree_cola():
    pays = s.payout_schedule(1000, 5, 1.02, deferral_years=2)
    assert pays == pytest.approx([0, 0, 1000, 1020, 1040.4])
    r = s.run_simulation(**CASE_A, index_returns_rate=1.07, retiree_cola=1.02, deferral_years=3)
    ret = r["yearly_data"][r["yearly_data"]["Year"].str.startswith("R")]
    assert (ret["Pension Redeemed"].iloc[:3] == 0).all()
    assert ret["Pension Redeemed"].iloc[4] == pytest.approx(CASE_A["starting_allowance"] * 1.02)


def test_refund_with_interest():
    assert s.refund_with_interest([100, 100], 10) == pytest.approx(210)


# --- Allowance estimator -----------------------------------------------------------

def test_estimate_allowance_formula_and_vesting():
    assert s.estimate_allowance(30, 100000, 2.0) == pytest.approx(60000)
    assert s.estimate_allowance(30, 100000, 2.0, early_reduction_pct=10) == pytest.approx(54000)
    assert s.estimate_allowance(4, 100000, 2.0, vesting_years=5) == 0.0
    assert s.estimate_allowance(5, 100000, 2.0, vesting_years=5) == pytest.approx(10000)


def test_todays_dollars_grow_by_cola_to_retirement():
    assert s.to_retirement_dollars(70000, 30, 1.03) == pytest.approx(70000 * 1.03 ** 30)
    assert s.to_retirement_dollars(70000, 30, 1.0) == pytest.approx(70000)


# --- Shortfall after depletion ------------------------------------------------------

def test_negative_balance_earns_no_returns():
    r = _run(CASE_B, 1.05)
    ret = r["yearly_data"][r["yearly_data"]["Year"].str.startswith("R")]
    negative_start = ret[ret["Start Balance"] < 0]
    assert len(negative_start) > 0
    assert (negative_start["Market Returns"] == 0).all()
    # Once negative, each year only adds that year's unpaid withdrawal.
    expected = negative_start["Start Balance"] - negative_start["Pension Redeemed"]
    assert negative_start["Balance"].to_numpy() == pytest.approx(expected.to_numpy())


# --- Break-even cap --------------------------------------------------------------

def test_breakeven_is_infinite_when_no_return_can_save_the_fund():
    # One working year of deposits, then a huge withdrawal right away.
    hopeless = dict(CASE_B, work_years=1, retirement_years=1, starting_allowance=10_000_000)
    args = tuple(hopeless[k] for k in (
        "starting_wage", "work_years", "cola_increase", "step_increase", "promotion_years",
        "promotion_increase", "pension_contribution_rate", "starting_allowance", "retirement_years"))
    assert math.isinf(s.compute_breakeven_rate(*args))


# --- Monte Carlo return model ----------------------------------------------------

def test_lognormal_returns_match_requested_median_and_spread():
    mean, std = 0.07, 0.15
    sigma = s.lognormal_sigma(mean, std)
    draws = np.exp(np.random.default_rng(1).normal(math.log(1 + mean), sigma, 2_000_000)) - 1
    assert np.median(draws) == pytest.approx(mean, abs=1e-3)
    assert draws.std() == pytest.approx(std, abs=1e-3)
    assert draws.min() > -1.0


def test_monte_carlo_typical_working_path_tracks_flat_rate():
    # With contributions only, the median path should sit close to the flat
    # line (the input is read as the same compound rate on both pages), not
    # far below it as an arithmetic-mean model would put it.
    flat = _run(CASE_A, 1.07)["personal_fund_values"][CASE_A["work_years"]]
    mc = s.run_monte_carlo(**CASE_A, mean_return=0.07, std_return=0.15, n_simulations=4000)
    assert mc["median_path"][CASE_A["work_years"]] == pytest.approx(flat, rel=0.08)
