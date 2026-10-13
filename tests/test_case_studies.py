"""Checks that the case-study copy, the presets, and the engine agree.

Each case study's one-click preset is replayed through the same estimator
and simulation the sidebar uses, and the headline claims in its copy are
checked against the result. If an engine or preset change moves a number,
these fail so the copy gets updated with it.
"""

import pytest

import common
import simulation as s
from view_market_swings import risk_tier


def _replay(preset_id):
    v = common.PRESETS[preset_id]["values"]
    assert v["in_allowance_mode"] == "Estimate for me"
    promo = tuple(int(x) for x in v["in_promo_years"].split(",") if x.strip())
    cola = 1 + v["in_cola"] / 100
    step = 1 + v["in_step"] / 100
    promo_inc = 1 + v["in_promo_pct"] / 100
    wy, age = v["in_retirement_age"] - v["in_hire_age"], v["in_retirement_age"]
    fas = s.compute_fas(v["in_wage"], wy, cola, step, promo, promo_inc,
                        v["in_step_count"], v["in_step_midyear"])
    plan = s.plan_benefit(wy, age, fas)
    assert plan["status"] == "immediate"  # every case study retires at an eligible age
    allowance = plan["allowance"]
    inflation = 1 + v["in_inflation"] / 100
    kw = dict(step_count=v["in_step_count"], first_step_midyear=v["in_step_midyear"],
              retiree_cola=1 + min(v["in_inflation"], s.PLAN_RETIREE_COLA_CAP_PCT) / 100)
    args = (v["in_wage"], wy, cola, step, promo, promo_inc,
            v["in_contrib"] / 100, allowance, v["in_retirement_years"])
    res = s.run_simulation(*args, 1 + v["in_returns"] / 100, **kw)
    pv = res["personal_fund_values"]
    depletion = next((k for k in range(1, v["in_retirement_years"] + 1) if pv[wy + k] <= 0), None)
    return {
        "factor": plan["factor_pct"],
        "allowance": allowance,
        # First payment is at the end of the first retirement year (the app's
        # single timing convention for today's-dollar conversions).
        "allowance_today": allowance / inflation ** (wy + 1),
        "received": res["pension_redeemed_total"],
        "at_retirement": pv[wy],
        "final": res["personal_balance"],
        "depletion": depletion,
        "breakeven": s.compute_breakeven_rate(*args, **kw),
    }


# (preset, personal fund wins?, plan factor, allowance, today's dollars,
#  total received, fund at retirement, final balance or None, depletion year or None)
CLAIMS = [
    ("alice", True, 2.0, 238_100, 110_700, 9.7e6, 3.2e6, 10.0e6, None),
    ("bob", False, 1.5, 41_100, 24_500, 2.1e6, 332_000, None, 10),
    ("carol", True, 2.0, 198_800, 81_700, 6.4e6, 2.9e6, 5.2e6, None),
    ("dave", False, 2.0, 51_900, 34_900, 1.7e6, 276_000, None, 6),
    ("frank", True, 1.5, 166_500, 87_600, 5.3e6, 2.4e6, 6.5e6, None),
    ("grace", False, 2.0, 40_100, 28_400, 1.3e6, 251_000, None, 8),
]


@pytest.mark.parametrize("preset,b_wins,factor,allow,today,received,at_ret,final,dep", CLAIMS)
def test_case_study_copy_matches_engine(preset, b_wins, factor, allow, today, received, at_ret, final, dep):
    r = _replay(preset)
    assert (r["final"] > 0) == b_wins
    assert r["factor"] == factor
    assert r["allowance"] == pytest.approx(allow, rel=0.005)
    assert r["allowance_today"] == pytest.approx(today, rel=0.005)
    assert r["received"] == pytest.approx(received, rel=0.03)
    assert r["at_retirement"] == pytest.approx(at_ret, rel=0.03)
    if final is not None:
        # Copy says "above" / "near" these figures.
        assert r["final"] == pytest.approx(final, rel=0.03)
    assert r["depletion"] == dep


def test_grace_breakeven_claim():
    # Copy: "would need a steady 12.5% a year just to break even."
    assert round(_replay("grace")["breakeven"], 1) == 12.5


def test_alice_breakeven_claim():
    # Copy: "at a flat 9.2% or less, the pension comes out ahead."
    assert 9.2 < _replay("alice")["breakeven"] < 9.3


@pytest.mark.parametrize("preset,out_of_100", [("alice", 38), ("carol", 34), ("frank", 31), ("grace", 97)])
def test_case_study_market_swing_claims(preset, out_of_100):
    # Copy: "runs out in about N out of 100 possible futures" at the page's
    # default 15% swings.
    v = common.PRESETS[preset]["values"]
    promo = tuple(int(x) for x in v["in_promo_years"].split(",") if x.strip())
    cola, step, promo_inc = 1 + v["in_cola"] / 100, 1 + v["in_step"] / 100, 1 + v["in_promo_pct"] / 100
    wy = v["in_retirement_age"] - v["in_hire_age"]
    fas = s.compute_fas(v["in_wage"], wy, cola, step, promo, promo_inc)
    allowance = s.plan_benefit(wy, v["in_retirement_age"], fas)["allowance"]
    mc = s.run_monte_carlo(
        v["in_wage"], wy, cola, step, promo, promo_inc, v["in_contrib"] / 100,
        allowance, v["in_retirement_years"], mean_return=v["in_returns"] / 100, std_return=0.15,
        n_simulations=1000, retiree_cola=1.02)
    assert round(mc["depletion_prob"] * 100) == out_of_100


# --- Risk verdict tiers ----------------------------------------------------------

@pytest.mark.parametrize("prob,flat_b_wins,tier", [
    (0.0, True, "none"),
    (0.001, True, "small"),   # one failed future is not "none"
    (0.10, True, "small"),
    (0.11, True, "tradeoff"),
    (0.25, True, "tradeoff"),
    (0.50, True, "lean_a"),
    (0.51, True, "a_safer"),
    (0.955, False, "a_confirmed"),  # flat-rate pension win never claims B "wins"
    (0.40, False, "a_close"),
])
def test_risk_tier_boundaries(prob, flat_b_wins, tier):
    assert risk_tier(prob, flat_b_wins) == tier


def test_share_formatting_never_rounds_real_risk_to_zero():
    assert common.fmt_share(0.003) == "0.3%"
    assert common.fmt_share(0.0) == "0%"
    assert common.fmt_share(0.36) == "36%"


# --- Shareable links ---------------------------------------------------------------

def test_query_param_parsing_rejects_bad_values():
    spec = common._SHARE_SPEC
    assert common._parse_param("30", spec["in_hire_age"]) == 30
    assert common._parse_param("7.5", spec["in_returns"]) == 7.5
    assert common._parse_param("99", spec["in_returns"]) is None      # above widget max
    assert common._parse_param("abc", spec["in_wage"]) is None
    assert common._parse_param("nan", spec["in_returns"]) is None
    assert common._parse_param("True", spec["in_real"]) is True
    assert common._parse_param("Enter manually", spec["in_allowance_mode"]) == "Enter manually"
    assert common._parse_param("Hack", spec["in_allowance_mode"]) is None


# --- Today's dollars ---------------------------------------------------------------

def test_deflated_results_are_consistent():
    inputs = {"inflation": 1.025, "work_years": 30, "retirement_years": 30, "retirement_age": 55,
              "hire_year": common.CURRENT_YEAR}
    res = s.run_simulation(120000, 30, 1.03, 1.055, (10, 20), 1.08, 0.10, 238100, 30, 1.10,
                           retiree_cola=1.02)
    real = common.deflate_results(res, inputs)
    assert real["personal_balance"] == pytest.approx(res["personal_balance"] / 1.025 ** 60)
    assert real["pension_fund_values"][-1] == pytest.approx(real["pension_redeemed_total"])
    assert real["pension_redeemed_total"] < res["pension_redeemed_total"]
    assert common.ages_for(inputs)[0] == 25 and common.ages_for(inputs)[30] == 55


def test_deflation_is_anchored_to_this_calendar_year():
    # Hired 10 years ago: chart point 10 is (roughly) now, so it is unchanged;
    # earlier points grow and later points shrink.
    inputs = {"inflation": 1.03, "work_years": 30, "retirement_years": 20, "retirement_age": 60,
              "hire_year": common.CURRENT_YEAR - 10}
    d = common._deflators(inputs, 51)
    assert d[10] == pytest.approx(1.0)
    assert d[0] == pytest.approx(1.03 ** -10)
    assert d[50] == pytest.approx(1.03 ** 40)
    assert common.calendar_years_for(inputs)[11] == common.CURRENT_YEAR


def test_wage_today_inverts_to_starting_wage():
    # The sidebar divides today's wage by the growth factor of this career
    # year; replaying the schedule from that start must land back on it.
    args = (1.03, 1.055, (10,), 1.08, 4, True)
    year_now = 13
    growth = s.salary_schedule(1.0, year_now, *args)[-1]
    start = 150000 / growth
    assert s.salary_schedule(start, year_now, *args)[-1] == pytest.approx(150000)


def test_out_of_100_never_hides_a_real_risk():
    assert common.out_of_100(0.003) == "fewer than 1"
    assert common.out_of_100(0.0) == "0"
    assert common.out_of_100(0.384) == "38"


def test_old_links_with_years_of_work_still_load():
    assert common.legacy_hire_age("30", 55) == 25
    assert common.legacy_hire_age("15", 63) == 48
    assert common.legacy_hire_age(None, 55) is None
    assert common.legacy_hire_age("abc", 55) is None
    assert common.legacy_hire_age("50", 55) is None   # hire age 5 is out of range


def test_todays_dollar_shortfall_converts_each_missed_payment_in_its_own_year():
    # Alice at 0% returns runs out. Her shortfall in this year's dollars must
    # equal the sum of each unpaid payment converted in the year it was due.
    inputs = {"inflation": 1.025, "work_years": 30, "retirement_years": 30, "retirement_age": 55,
              "hire_year": common.CURRENT_YEAR}
    res = s.run_simulation(120000, 30, 1.03, 1.055, (10, 20), 1.08, 0.10, 238100, 30, 1.0,
                           retiree_cola=1.02)
    df = res["yearly_data"]
    expected = 0.0
    for i in range(len(df)):
        start, end = df["Start Balance"].iloc[i], df["Balance"].iloc[i]
        if end < 0:
            unpaid = -end if start >= 0 else start - end
            expected -= unpaid / 1.025 ** (i + 1)
    real = common.deflate_results(res, inputs)
    assert real["personal_balance"] == pytest.approx(expected)
    # The old shortcut (divide the whole nominal shortfall by the last year's
    # inflation) understated it by about a quarter here.
    assert abs(real["personal_balance"]) > abs(res["personal_balance"] / 1.025 ** 60) * 1.2


def test_reference_line_plots_each_years_payout():
    inputs = {"inflation": 1.025, "work_years": 30, "retirement_years": 30, "retirement_age": 55,
              "hire_year": common.CURRENT_YEAR}
    res = s.run_simulation(120000, 30, 1.03, 1.055, (10, 20), 1.08, 0.10, 238100, 30, 1.07,
                           retiree_cola=1.02)
    res = {**res, "index_return_pct": 7.0}
    fig = common.build_fund_chart(inputs, res, show_ref_line=True)
    payout = next(tr for tr in fig.data if tr.name.startswith("Pension paid each year"))
    last_payment = res["yearly_data"]["Pension Redeemed"].iloc[-1]
    assert payout.y[-1] == pytest.approx(last_payment)
    assert max(payout.y) < res["pension_redeemed_total"] / 5   # not the running total
    assert fig.layout.yaxis.range[1] >= max(payout.y)           # fully on the chart


def test_sheet_writes_are_capped_site_wide(monkeypatch):
    monkeypatch.setattr(common, "_sheet_write_times", common.collections.deque())
    allowed = [common._sheet_write_allowed() for _ in range(common._SHEET_WRITES_PER_MINUTE + 5)]
    assert allowed.count(True) == common._SHEET_WRITES_PER_MINUTE
    assert allowed[-1] is False


def test_account_chart_and_table_show_cash_not_negative_debt():
    inputs = {"inflation": 1.025, "work_years": 2, "retirement_years": 5,
              "retirement_age": 60, "hire_year": common.CURRENT_YEAR}
    res = s.run_simulation(100000, 2, 1.0, 1.0, (), 1.0, 0.1, 10000, 5, 1.0)
    res["index_return_pct"] = 0.0
    fig = common.build_fund_chart(inputs, res, show_ref_line=False)
    account = next(tr for tr in fig.data if tr.name.startswith("Steady"))
    assert list(account.y) == [0, 10000, 20000, 10000, 0, 0, 0, 0]
    table = common.account_payment_table(res["yearly_data"])
    retirement = table[table.Year.str.startswith("R")]
    assert list(retirement["Income Unpaid"]) == [0, 0, 10000, 10000, 10000]
    assert list(retirement["Start Balance"] + retirement["Market Returns"] - retirement["Account Withdrawal"]) == list(retirement["Balance"])
    assert retirement["Income Unpaid"].sum() == -res["personal_balance"]


@pytest.mark.parametrize("depleted", [0.0, 1.0])
def test_zero_swings_never_claims_bad_markets(depleted, monkeypatch):
    import view_market_swings
    html = []
    monkeypatch.setattr(view_market_swings, "render_html", html.append)
    view_market_swings.render_risk_verdict(depleted, 7.0, 0.0, flat_b_wins=not depleted)
    assert "every simulation repeats" in html[0]
    assert "bad markets" not in html[0] and "real ups and downs" not in html[0]
    assert ("cannot cover" in html[0]) == bool(depleted)


def test_inflation_adjusted_cash_flows_match_nominal_engine_without_double_counting():
    # Two $10,000 deposits, then $5,000 and $5,100 withdrawals. A 7% nominal
    # return applies to existing money before each end-of-year cash flow.
    inputs = {"inflation": 1.025, "work_years": 2, "retirement_years": 2,
              "retirement_age": 60, "hire_year": common.CURRENT_YEAR}
    nominal = s.run_simulation(100000, 2, 1.0, 1.0, (), 1.0, 0.1, 5000, 2, 1.07,
                               retiree_cola=1.02)
    assert nominal["personal_balance"] == pytest.approx(13249.43)
    real = common.deflate_results(nominal, inputs)
    balance = 0.0
    for year, cash_flow in enumerate([10000, 10000, -5000, -5100], start=1):
        balance = balance * (1.07 / 1.025) + cash_flow / 1.025 ** year
    assert real["personal_balance"] == pytest.approx(balance)
    assert real["personal_balance"] == pytest.approx(13249.43 / 1.025 ** 4)
