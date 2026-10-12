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
    fas = s.compute_fas(v["in_wage"], v["in_work_years"], cola, step, promo, promo_inc,
                        v["in_step_count"], v["in_step_midyear"])
    allowance = s.estimate_allowance(v["in_work_years"], fas, v["in_factor"],
                                     v["in_early_red"], v["in_vest"])
    args = (v["in_wage"], v["in_work_years"], cola, step, promo, promo_inc,
            v["in_contrib"] / 100, allowance, v["in_retirement_years"])
    res = s.run_simulation(*args, 1 + v["in_returns"] / 100,
                           v["in_step_count"], v["in_step_midyear"])
    pv = res["personal_fund_values"]
    wy = v["in_work_years"]
    depletion = next((k for k in range(1, v["in_retirement_years"] + 1) if pv[wy + k] <= 0), None)
    return {
        "allowance": allowance,
        "allowance_today": allowance / cola ** wy,
        "received": res["pension_redeemed_total"],
        "at_retirement": pv[wy],
        "final": res["personal_balance"],
        "depletion": depletion,
        "breakeven": s.compute_breakeven_rate(*args, v["in_step_count"], v["in_step_midyear"]),
    }


# (preset, personal fund wins?, allowance, today's dollars, total received,
#  fund at retirement, final balance or None, depletion year or None)
CLAIMS = [
    ("alice", True, 238_100, 98_100, 11.3e6, 3.2e6, 5.4e6, None),
    ("bob", False, 54_850, 30_400, 4.1e6, 332_000, None, 7),
    ("carol", True, 198_800, 70_600, 7.2e6, 2.9e6, 3.4e6, None),
    ("dave", False, 51_900, 33_300, 3.1e6, 276_000, None, 6),
    ("frank", True, 166_500, 79_500, 6.1e6, 2.4e6, 4.8e6, None),
]


@pytest.mark.parametrize("preset,b_wins,allow,today,received,at_ret,final,dep", CLAIMS)
def test_case_study_copy_matches_engine(preset, b_wins, allow, today, received, at_ret, final, dep):
    r = _replay(preset)
    assert (r["final"] > 0) == b_wins
    assert r["allowance"] == pytest.approx(allow, rel=0.005)
    assert r["allowance_today"] == pytest.approx(today, rel=0.005)
    assert r["received"] == pytest.approx(received, rel=0.03)
    assert r["at_retirement"] == pytest.approx(at_ret, rel=0.03)
    if final is not None:
        # Copy says "above" / "near" these figures.
        assert r["final"] == pytest.approx(final, rel=0.03)
    assert r["depletion"] == dep


def test_alice_breakeven_claim():
    # Copy: "at a flat 9.6% or less, the pension comes out ahead."
    assert _replay("alice")["breakeven"] == pytest.approx(9.6, abs=0.05)


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
