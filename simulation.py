"""Pure financial-simulation core for the pension calculator.

This module intentionally has **no** Streamlit dependency and no module-level
side effects, so the math can be imported and unit-tested outside the UI.
Caching (``st.cache_data``) is applied by the app layer, not here.

Rate conventions (kept for backward compatibility with the app):
- ``cola_increase``, ``step_increase``, ``promotion_increase`` and
  ``index_returns_rate`` are **multipliers** (e.g. 1.03 for a 3% COLA).
- ``pension_contribution_rate`` is a plain fraction (e.g. 0.10).
- ``index_returns_rate`` is a compound (geometric) annual rate: the flat path
  grows by exactly this much every year, and the Monte Carlo median year does
  too, so both pages read the same input the same way.
- ``retiree_cola`` (a multiplier) grows the pension in retirement and is
  separate from the salary ``cola_increase``. ``None`` means "same as salary".
- ``deferral_years`` is how many retirement years pass before the pension
  starts (a deferred pension). Option B withdraws nothing in those years.
"""

import math

import numpy as np
import pandas as pd


def salary_schedule(starting_wage, work_years, cola_increase, step_increase,
                    promotion_years, promotion_increase, step_count=4,
                    first_step_midyear=True):
    """Effective annual salary for each working year.

    Single source of truth for the salary-evolution logic (step raises at the
    end of each of the first ``step_count`` years, optional year-1 half-step
    averaging when the first raise lands mid-year, and promotion-year
    multipliers). Consumed by :func:`run_simulation`, :func:`compute_fas`, and
    :func:`run_monte_carlo` so the three can never drift apart.
    """
    salaries = []
    salary = starting_wage
    for yr in range(1, work_years + 1):
        if yr == 1 and first_step_midyear and step_count >= 1:
            effective = salary * (1 + step_increase) / 2
        else:
            effective = salary
        salaries.append(effective)
        salary *= cola_increase
        if yr <= step_count:
            salary *= step_increase
        if yr in promotion_years:
            salary *= promotion_increase
    return salaries


def payout_schedule(starting_allowance, retirement_years, retiree_cola,
                    deferral_years=0):
    """Pension paid in each retirement year, which Option B also withdraws.

    Nothing is paid during the first ``deferral_years``; after that the
    allowance starts at ``starting_allowance`` and grows by ``retiree_cola``.
    """
    payouts = []
    payment = starting_allowance
    for k in range(retirement_years):
        if k < deferral_years:
            payouts.append(0.0)
        else:
            payouts.append(payment)
            payment *= retiree_cola
    return payouts


def run_simulation(starting_wage, work_years, cola_increase, step_increase,
                   promotion_years, promotion_increase, pension_contribution_rate,
                   starting_allowance, retirement_years, index_returns_rate,
                   step_count=4, first_step_midyear=True, retiree_cola=None,
                   deferral_years=0):
    """Flat-rate simulation of both options, year by year.

    Once Option B's balance goes negative it stops earning (or owing) market
    returns, so a negative balance is the running total of withdrawals the
    fund could not pay, not a debt compounding at the market rate.
    """
    pension_contribution_total = 0
    pension_redeemed_total = 0
    personal_balance = 0
    payouts = payout_schedule(
        starting_allowance, retirement_years,
        cola_increase if retiree_cola is None else retiree_cola, deferral_years)

    salaries = salary_schedule(starting_wage, work_years, cola_increase,
                               step_increase, promotion_years, promotion_increase,
                               step_count, first_step_midyear)

    rows = []

    # Work phase
    for work_year in range(1, work_years + 1):
        effective_salary = salaries[work_year - 1]

        pension_contribution_this_year = effective_salary * pension_contribution_rate
        pension_contribution_total += pension_contribution_this_year

        start_balance = personal_balance
        market_returns = personal_balance * (index_returns_rate - 1)
        personal_balance = personal_balance + market_returns + pension_contribution_this_year

        rows.append({
            "Year": f"W{work_year}",
            "Salary": effective_salary,
            "Start Balance": start_balance,
            "Pension Contribution": pension_contribution_this_year,
            "Pension Contribution Total": pension_contribution_total,
            "Pension Redeemed": 0.0,
            "Pension Redeemed Total": 0.0,
            "Market Returns": market_returns,
            "Balance": personal_balance,
        })

    # Retirement phase
    for ret_year in range(1, retirement_years + 1):
        pension_redeemed = payouts[ret_year - 1]
        pension_redeemed_total += pension_redeemed

        start_balance = personal_balance
        market_returns = max(personal_balance, 0.0) * (index_returns_rate - 1)
        personal_balance = personal_balance - pension_redeemed + market_returns

        rows.append({
            "Year": f"R{ret_year}",
            "Salary": float("nan"),
            "Start Balance": start_balance,
            "Pension Contribution": 0.0,
            "Pension Contribution Total": 0.0,
            "Pension Redeemed": pension_redeemed,
            "Pension Redeemed Total": pension_redeemed_total,
            "Market Returns": market_returns,
            "Balance": personal_balance,
        })

    yearly_data = pd.DataFrame(rows)

    # Chart arrays are derived from the single yearly_data source of truth,
    # with a "W0" anchor row at $0 prepended. No parallel positional lists.
    years = ["W0"] + yearly_data["Year"].tolist()
    pension_fund_values = [0] + yearly_data["Pension Redeemed Total"].tolist()
    personal_fund_values = [0] + yearly_data["Balance"].tolist()

    return {
        "years": years,
        "pension_fund_values": pension_fund_values,
        "personal_fund_values": personal_fund_values,
        "yearly_data": yearly_data,
        "pension_contribution_total": pension_contribution_total,
        "pension_redeemed_total": pension_redeemed_total,
        "personal_balance": personal_balance,
    }


def compute_fas(starting_wage, work_years, cola_increase, step_increase,
                promotion_years, promotion_increase, step_count=4,
                first_step_midyear=True):
    """Final average salary: the highest 3 consecutive years of pay."""
    sal_hist = salary_schedule(starting_wage, work_years, cola_increase,
                               step_increase, promotion_years, promotion_increase,
                               step_count, first_step_midyear)
    if len(sal_hist) >= 3:
        return max(sum(sal_hist[i:i + 3]) / 3 for i in range(len(sal_hist) - 2))
    return sum(sal_hist) / len(sal_hist) if sal_hist else starting_wage


def estimate_allowance(work_years, fas, factor_pct, early_reduction_pct=0.0,
                       vesting_years=0):
    """First-year allowance from a final-average-salary formula.

    Years of Service x Final Average Salary x Retirement Factor x (1 - early
    reduction). Returns 0 when the career is shorter than ``vesting_years``,
    since an unvested member gets no lifetime allowance.
    """
    if work_years < vesting_years:
        return 0.0
    return work_years * fas * (factor_pct / 100.0) * (1.0 - early_reduction_pct / 100.0)


# --- Built-in plan rules ---------------------------------------------------------
# The plan's rules for members hired on or after January 1, 2014, taken from
# the plan's member handbook (rev. November 2022) and its July 1, 2026
# actuarial valuation (summary of plan provisions).

PLAN_FIRST_HIRE_YEAR = 2014        # these rules cover members hired this year or later
PLAN_CONTRIBUTION_PCT = 10.0       # member contribution, % of pay
PLAN_BENEFIT_CAP = 0.80            # allowance capped at 80% of final average salary
PLAN_RETIREE_COLA_CAP_PCT = 2.0    # retiree COLA follows CPI, up to 2% a year
PLAN_REFUND_INTEREST_PCT = 6.5     # interest credited on refunded contributions
PLAN_VESTING_YEARS = 5
PLAN_FULL_AGE = 60                 # earliest age for a pension without 30 years
PLAN_SERVICE_FOR_ANY_AGE = 30


def early_reduction_factor(age):
    """The plan's early-retirement reduction factor at a whole-year age.

    1.0 from age 60; 1.5 points less per year from 55 to 59 (0.925 at 55);
    3 points less per year below 55 (0.895 at 54, 0.715 at 48).
    """
    if age >= 60:
        return 1.0
    if age >= 55:
        return 0.925 + 0.015 * (age - 55)
    return max(0.0, 0.925 - 0.03 * (55 - age))


def plan_benefit(work_years, retirement_age, fas):
    """First-year allowance under the built-in plan rules.

    Returns a dict with the ``allowance`` (first year it is paid), the
    ``factor_pct`` and ``reduction`` applied, whether the 80% ``capped`` limit
    bit, ``deferral_years`` before payments start, whether the retiree
    ``cola_applies``, and a ``status`` of "immediate", "deferred", or
    "unvested" (no pension; contributions are refunded with interest).
    """
    result = {"factor_pct": 0.0, "reduction": 1.0, "capped": False,
              "deferral_years": 0, "cola_applies": True, "status": "immediate"}
    if work_years >= PLAN_SERVICE_FOR_ANY_AGE:
        result["factor_pct"] = 2.1 if retirement_age >= 63 else 2.0
        # Unreduced from age 55 with 30 years of service.
        if retirement_age < 55:
            result["reduction"] = early_reduction_factor(retirement_age)
    elif work_years >= PLAN_VESTING_YEARS and retirement_age >= 63:
        result["factor_pct"] = 2.0
    elif work_years >= PLAN_VESTING_YEARS and retirement_age >= PLAN_FULL_AGE:
        result["factor_pct"] = 1.5
    elif work_years >= PLAN_VESTING_YEARS:
        # Too young to retire: a deferred pension starts at 60 at 1.5%, with
        # no retiree COLA and no spouse continuance.
        result.update(factor_pct=1.5, status="deferred", cola_applies=False,
                      deferral_years=PLAN_FULL_AGE - retirement_age)
    else:
        result.update(status="unvested", cola_applies=False)
        result["allowance"] = 0.0
        return result

    raw = work_years * fas * result["factor_pct"] / 100.0 * result["reduction"]
    cap = PLAN_BENEFIT_CAP * fas
    result["capped"] = raw > cap
    result["allowance"] = min(raw, cap)
    return result


def refund_with_interest(contributions, interest_pct=PLAN_REFUND_INTEREST_PCT):
    """Value of yearly contributions refunded with interest at separation."""
    balance = 0.0
    for c in contributions:
        balance = balance * (1 + interest_pct / 100.0) + c
    return balance


def to_retirement_dollars(amount_today, work_years, inflation):
    """Grow a today's-dollars amount by inflation (a multiplier) to the first year of retirement."""
    return amount_today * inflation ** work_years


# Break-even search window, in percent. A fund that survives at 0% has a
# break-even of 0; one that still fails at the cap reports ``math.inf``.
BREAKEVEN_CAP_PCT = 100.0


def compute_breakeven_rate(starting_wage, work_years, cola_increase, step_increase,
                            promotion_years, promotion_increase, pension_contribution_rate,
                            starting_allowance, retirement_years, step_count=4,
                            first_step_midyear=True, retiree_cola=None,
                            deferral_years=0):
    """Lowest flat annual return (%) at which Option B lasts all of retirement."""
    def survives(rate):
        return run_simulation(
            starting_wage, work_years, cola_increase, step_increase,
            promotion_years, promotion_increase, pension_contribution_rate,
            starting_allowance, retirement_years, 1.0 + rate,
            step_count, first_step_midyear, retiree_cola, deferral_years,
        )["personal_balance"] > 0

    if survives(0.0):
        return 0.0
    cap = BREAKEVEN_CAP_PCT / 100.0
    if not survives(cap):
        return math.inf
    lo, hi = 0.0, cap
    for _ in range(40):
        mid = (lo + hi) / 2
        if survives(mid):
            hi = mid
        else:
            lo = mid
    return hi * 100


def lognormal_sigma(mean_return, std_return):
    """Log-space sigma giving yearly returns a standard deviation of ``std_return``.

    Yearly growth factors are lognormal with median ``1 + mean_return``, so
    the typical year compounds at exactly the flat rate. For a lognormal with
    median m and log-sigma s, Var = m^2 * x * (x - 1) where x = exp(s^2);
    solving the quadratic for x gives s.
    """
    m = 1.0 + mean_return
    x = (1.0 + math.sqrt(1.0 + 4.0 * std_return ** 2 / m ** 2)) / 2.0
    return math.sqrt(math.log(x))


def run_monte_carlo(starting_wage, work_years, cola_increase, step_increase,
                    promotion_years, promotion_increase, pension_contribution_rate,
                    starting_allowance, retirement_years, mean_return, std_return,
                    n_simulations, seed=42, step_count=4, first_step_midyear=True,
                    retiree_cola=None, deferral_years=0):
    """Replay the flat-rate schedule through randomized market histories.

    ``mean_return`` is the same compound rate the flat page uses: yearly
    growth factors are lognormal with that median, so with no withdrawals
    the typical path compounds exactly like the flat line, and any gap in
    retirement comes from the order of good and bad years. ``std_return`` is
    the standard deviation of a single year's return. Lognormal growth can
    never fall below -100%, so no clipping is needed.
    """
    rng = np.random.default_rng(seed)
    total_years = work_years + retirement_years

    # Annual return multipliers: shape (n_simulations, total_years)
    sigma = lognormal_sigma(mean_return, std_return)
    mults = np.exp(rng.normal(math.log(1.0 + mean_return), sigma,
                              (n_simulations, total_years)))

    # history[year, sim] = fund balance at end of that year
    history = np.zeros((total_years + 1, n_simulations))

    salaries = salary_schedule(starting_wage, work_years, cola_increase,
                               step_increase, promotion_years, promotion_increase,
                               step_count, first_step_midyear)
    for wy in range(1, work_years + 1):
        contribution = salaries[wy - 1] * pension_contribution_rate
        history[wy] = history[wy - 1] * mults[:, wy - 1] + contribution

    payouts = payout_schedule(
        starting_allowance, retirement_years,
        cola_increase if retiree_cola is None else retiree_cola, deferral_years)
    for ry in range(1, retirement_years + 1):
        idx = work_years + ry
        grown = history[idx - 1] * mults[:, idx - 1] - payouts[ry - 1]
        # Depletion is absorbing: once a path hits $0 it stays there, rather than
        # compounding a fictitious negative "debt" at the market rate.
        history[idx] = np.maximum(grown, 0.0)

    pcts = np.percentile(history, [5, 25, 75, 95], axis=1)
    median_path = np.percentile(history, 50, axis=1)

    # Per-path first retirement year with a $0 balance (0 = never ran out).
    # Depletion is absorbing (see above), so "hit $0 at any point" and "ended
    # at $0" are the same set of paths.
    ret_hist = history[work_years + 1:]
    ran_out = ret_hist <= 0
    any_out = ran_out.any(axis=0)
    depletion_years = np.where(any_out, ran_out.argmax(axis=0) + 1, 0)

    # Share of simulated futures that ran out of money by the end of retirement.
    depletion_prob = float(any_out.mean())

    return {
        "percentiles": pcts,
        "depletion_prob": depletion_prob,
        "median_path": median_path,
        "final_balances": history[-1],
        "balances_at_leaving": history[work_years].copy(),
        "depletion_years": depletion_years,
    }
