"""Pure financial-simulation core for the pension calculator.

This module intentionally has **no** Streamlit dependency and no module-level
side effects, so the math can be imported and unit-tested outside the UI.
Caching (``st.cache_data``) is applied by the app layer, not here.

Rate conventions (kept for backward compatibility with the app):
- ``cola_increase``, ``step_increase``, ``promotion_increase`` and
  ``index_returns_rate`` are **multipliers** (e.g. 1.03 for a 3% COLA).
- ``pension_contribution_rate`` is a plain fraction (e.g. 0.10).
"""

import numpy as np
import pandas as pd


def salary_schedule(starting_wage, work_years, cola_increase, step_increase,
                    promotion_years, promotion_increase):
    """Effective annual salary for each working year.

    Single source of truth for the salary-evolution logic (year-1 half-step
    averaging, first-4-years step raises, and promotion-year multipliers).
    Consumed by :func:`run_simulation`, :func:`compute_fas`, and
    :func:`run_monte_carlo` so the three can never drift apart.
    """
    salaries = []
    salary = starting_wage
    for yr in range(1, work_years + 1):
        effective = salary * (1 + step_increase) / 2 if yr == 1 else salary
        salaries.append(effective)
        salary *= cola_increase
        if 1 <= yr < 5:
            salary *= step_increase
        if yr in promotion_years:
            salary *= promotion_increase
    return salaries


def run_simulation(starting_wage, work_years, cola_increase, step_increase,
                   promotion_years, promotion_increase, pension_contribution_rate,
                   starting_allowance, retirement_years, index_returns_rate):
    pension_contribution_total = 0
    pension_redeemed_total = 0
    personal_balance = 0
    pension_redeemed = starting_allowance

    salaries = salary_schedule(starting_wage, work_years, cola_increase,
                               step_increase, promotion_years, promotion_increase)

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
        pension_redeemed_total += pension_redeemed

        start_balance = personal_balance
        market_returns = personal_balance * (index_returns_rate - 1)
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

        pension_redeemed *= cola_increase

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
                promotion_years, promotion_increase):
    sal_hist = salary_schedule(starting_wage, work_years, cola_increase,
                               step_increase, promotion_years, promotion_increase)
    if len(sal_hist) >= 3:
        return max(sum(sal_hist[i:i + 3]) / 3 for i in range(len(sal_hist) - 2))
    return sum(sal_hist) / len(sal_hist) if sal_hist else starting_wage


def compute_breakeven_rate(starting_wage, work_years, cola_increase, step_increase,
                            promotion_years, promotion_increase, pension_contribution_rate,
                            starting_allowance, retirement_years):
    sim_args = (starting_wage, work_years, cola_increase, step_increase,
                promotion_years, promotion_increase, pension_contribution_rate,
                starting_allowance, retirement_years)
    if run_simulation(*sim_args, 1.0)["personal_balance"] > 0:
        return 0.0
    if run_simulation(*sim_args, 1.25)["personal_balance"] <= 0:
        return 25.0
    lo, hi = 0.0, 0.25
    for _ in range(30):
        mid = (lo + hi) / 2
        if run_simulation(*sim_args, 1.0 + mid)["personal_balance"] > 0:
            hi = mid
        else:
            lo = mid
    return hi * 100


def run_monte_carlo(starting_wage, work_years, cola_increase, step_increase,
                    promotion_years, promotion_increase, pension_contribution_rate,
                    starting_allowance, retirement_years, mean_return, std_return,
                    n_simulations, seed=42):
    rng = np.random.default_rng(seed)
    total_years = work_years + retirement_years

    # Annual return multipliers: shape (n_simulations, total_years), clipped so can't lose >100%
    raw = rng.normal(mean_return, std_return, (n_simulations, total_years))
    mults = np.clip(1.0 + raw, 0.0, None)

    # history[year, sim] = fund balance at end of that year
    history = np.zeros((total_years + 1, n_simulations))

    salaries = salary_schedule(starting_wage, work_years, cola_increase,
                               step_increase, promotion_years, promotion_increase)
    for wy in range(1, work_years + 1):
        contribution = salaries[wy - 1] * pension_contribution_rate
        history[wy] = history[wy - 1] * mults[:, wy - 1] + contribution

    pension_redeemed = starting_allowance
    for ry in range(1, retirement_years + 1):
        idx = work_years + ry
        grown = history[idx - 1] * mults[:, idx - 1] - pension_redeemed
        # Depletion is absorbing: once a path hits $0 it stays there, rather than
        # compounding a fictitious negative "debt" at the market rate.
        history[idx] = np.maximum(grown, 0.0)
        pension_redeemed *= cola_increase

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
        "depletion_years": depletion_years,
    }
