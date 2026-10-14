"""Page 2: what happens to your account when returns swing year to year.

The comparison page assumes the market returns one flat rate every single
year. This page re-runs the same scenario 1,000 times with realistic
year-to-year swings (a Monte Carlo simulation; that term appears in the
methodology expander, not in the main copy) and reports how often your account
runs out of money, when it happens, and what the typical outcome looks like.
"""

import math

import numpy as np
import streamlit as st

import simulation

from common import (
    build_fund_chart,
    chart_title,
    fund_chart_title,
    deflate_mc,
    inputs_summary_html,
    out_of_100,
    get_monte_carlo,
    render_feedback_form,
    render_html,
    render_dollar_toggle,
)


def risk_tier(depletion_prob, flat_b_wins):
    """Pick the verdict tier from the depletion share and the flat-rate winner.

    Kept free of Streamlit calls so the tier boundaries are unit-testable.
    """
    if not flat_b_wins:
        return "a_confirmed" if depletion_prob > 0.50 else "a_close"
    if depletion_prob == 0:
        return "none"
    if depletion_prob <= 0.10:
        return "small"
    if depletion_prob <= 0.25:
        return "tradeoff"
    if depletion_prob <= 0.50:
        return "lean_a"
    return "a_safer"


def render_risk_verdict(depletion_prob, current_rate_pct, std_pct, flat_b_wins):
    """The page's answer: a traffic-light verdict on the ruin risk.

    The comparison page answers "on average, does your account end with money?"
    The depletion probability answers "how often does your account run out once
    returns vary?" Those are different questions, and a favorable flat-rate
    result can coexist with an unacceptably high chance of ruin. This banner
    turns the two numbers into a single risk-tiered recommendation, with a
    ✓/⚠/✗ status so the tier is readable without relying on color alone.
    The wording depends on which option won at the flat rate, so the banner
    never claims a flat-rate result the first page did not show.
    """
    n = out_of_100(depletion_prob)
    r = f"{current_rate_pct:.1f}%"
    tier = risk_tier(depletion_prob, flat_b_wins)

    if std_pct == 0 and flat_b_wins:
        bg, bar, symbol = "#CCFBF1", "#0D9488", "✓"
        verdict = "With no ups and downs, every future matches page 1: your own account wins."
        body = (
            "The bumpiness slider is at 0%, so every simulated year returns exactly the same amount "
            "and your account never runs out. Move the slider right to see what market ups and downs do."
        )
    elif std_pct == 0:
        bg, bar, symbol = "#E0E7FF", "#4F46E5", ""
        verdict = "With no ups and downs, every future matches page 1: the pension wins."
        body = (
            f"The bumpiness slider is at 0%, so every simulated year returns exactly {r} and your account "
            "runs out in every future, just as on page 1. Move the slider right to see what market ups and downs do."
        )
    elif tier == "none":
        bg, bar, symbol = "#CCFBF1", "#0D9488", "✓"
        verdict = "No failures in these 1,000 futures."
        body = (
            "In all 1,000 possible futures with the ups and downs you chose, your account never ran "
            "out of money. That is a good sign, though not a guarantee: markets can be worse than "
            "anything in these simulations."
        )
    elif tier == "small":
        bg, bar, symbol = "#CCFBF1", "#0D9488", "✓"
        verdict = "Your account usually lasts, with a small risk of running out."
        body = (
            f"Your account ran out of money in <strong>{n} out of 100</strong> possible futures. "
            f"Most futures work out, but an unlucky one would leave you short late in life."
        )
    elif tier == "tradeoff":
        bg, bar, symbol = "#FEF3C7", "#D97706", "⚠"
        verdict = "A real trade-off: neither option is clearly better."
        body = (
            f"Your account usually ends with more money, but it ran out in <strong>{n} out of 100</strong> "
            f"possible futures. The pension can never run out. If running out of money in old age "
            f"would be a disaster for you, the pension's guarantee may be worth more than your account's "
            f"extra money."
        )
    elif tier == "lean_a":
        bg, bar, symbol = "#E0E7FF", "#4F46E5", ""
        verdict = "Your account runs out in a large share of futures, even though page 1 picked it."
        body = (
            f"Page 1 assumed a smooth {r} every year. With real ups and downs, your account ran out "
            f"of money in <strong>{n} out of 100</strong> possible futures. That is close to a coin "
            f"flip, while the pension pays for life no matter what."
        )
    elif tier == "a_safer":
        bg, bar, symbol = "#E0E7FF", "#4F46E5", ""
        verdict = "The pension is the safer choice."
        body = (
            f"Page 1 said your account wins with a smooth {r} every year. But with real ups and downs, "
            f"your account ran out of money in <strong>{n} out of 100</strong> possible futures. When "
            f"most futures end with an empty account, the pension's paycheck for life is the safer bet."
        )
    elif tier == "a_close":
        bg, bar, symbol = "#FEF3C7", "#D97706", "⚠"
        verdict = "The pension wins, though your account sometimes gets lucky."
        body = (
            f"Even with a smooth {r} every year, your account runs out. With real ups and downs it ran "
            f"out in <strong>{n} out of 100</strong> possible futures, and the rest only made it "
            f"because they happened to get good years. Choosing your own account here is a bet on luck; "
            f"the pension is the safer choice."
        )
    else:  # a_confirmed
        bg, bar, symbol = "#E0E7FF", "#4F46E5", ""
        verdict = "The pension is the safer choice, and bad markets make it clearer."
        body = (
            f"Even with a smooth {r} every year, your account runs out. With real ups and downs it ran "
            f"out in <strong>{n} out of 100</strong> possible futures. The pension's paycheck for "
            f"life is the more reliable choice."
        )

    if n == "0":
        headline = "🏆 Your own account wins in 100 out of 100 futures"
    elif n == "100":
        headline = "🏆 The pension wins in 100 out of 100 futures"
    elif n == "fewer than 1":
        headline = "Your own account wins in almost every future; the pension wins in fewer than 1 out of 100"
    else:
        headline = f"The pension wins in {n} out of 100 futures · Your own account wins in {100 - int(n)}"
    render_html(f"""
<div style="background-color:{bg}; border-left:5px solid {bar}; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<div style="font-size:1.4rem; font-weight:700; margin-bottom:0.6rem;">{headline}</div>
<strong>{symbol + " " if symbol else ""}{verdict}</strong><br><br>
{body}
</div>
""")


def render():
    inputs = st.session_state["_inputs"]
    res = st.session_state["_results"]
    index_return_pct = res["index_return_pct"]
    work_years = inputs["work_years"]
    retirement_years = inputs["retirement_years"]

    st.header("What If the Market Has Bad Years?")
    render_html(f"""
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
{inputs_summary_html(inputs, res)}
</div>
""")
    st.space("small")
    st.markdown(f"""
The steady-return page assumes investments grow by exactly {index_return_pct:.1f}% every single year before inflation. Real markets don't work that way; some years are way up and some are way down (say +18%, −4%, +25%, −12%), even if a typical year is still about {index_return_pct:.1f}%.

**So this page asks: with simulated ups and downs, how often does your own account win, and how often does the pension win?**

To find out, we made up **1,000 possible futures** for the stock market. Each one is a different random mix of good and bad years, like rolling dice for every year of your {work_years} working years and {retirement_years} retired years. Then we ran your plan through every one of them.
""")

    _mc_std_pct = st.slider(
        "How bumpy is the market?",
        min_value=0.0, max_value=30.0, value=15.0, step=0.5, format="%.1f%%",
        key="mc_std",
        help=(
            "How widely yearly returns vary. This is the standard deviation, not a maximum loss or gain. "
            "15% is an example assumption, not a prediction or a recommended investment mix. "
            "Slide left for a calmer market, right for a wilder one. At 0, every year is the same, "
            "just like page 1."
        ),
    )

    if _mc_std_pct == 0:
        st.caption(f"Every year returns exactly {index_return_pct:.1f}% before inflation.")
    else:
        _m = 1 + index_return_pct / 100
        _s = simulation.lognormal_sigma(index_return_pct / 100, _mc_std_pct / 100)
        def _pct(z):
            return f"{(_m * math.exp(z * _s) - 1) * 100:+.0f}%"
        st.caption(
            f"With this setting, about 2 out of 3 years return between {_pct(-1)} and {_pct(1)} before inflation. "
            f"About 1 year in 20 is worse than {_pct(-1.96)} or better than {_pct(1.96)}."
        )

    mc = get_monte_carlo(inputs, _mc_std_pct)
    if res.get("real_dollars"):
        mc = deflate_mc(mc, inputs)
    depletion_prob = mc["depletion_prob"]
    final_balances = mc["final_balances"]
    median_final = float(np.percentile(final_balances, 50))
    flat_final = res["personal_balance"]

    if inputs["plan_status"] == "unvested":
        # No pension, only a refund: the question becomes how often your own
        # account beats the refund on the day you leave.
        refund = res["refund"]
        wins = int((mc["balances_at_leaving"] > refund).sum())
        st.header("Your Result")
        render_dollar_toggle(inputs, res)
        render_html(f"""
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>You would get a refund, not a lifetime pension.</strong><br><br>
With the selected market swings, your own account ended up with more than the refund (about &#36;{refund:,.0f}) in
<strong>{out_of_100(wins / len(mc["balances_at_leaving"]))} out of 100</strong> possible futures. The refund grows at a
guaranteed {simulation.PLAN_REFUND_INTEREST_PCT:g}% a year, so your account has to beat that to come out ahead.
</div>
""")
        st.page_link(st.session_state["_pages"]["comparison"], label="**← Back to Steady Yearly Return**", icon="⚖️")
        render_feedback_form("market-swings")
        return

    st.header("Your Result")
    render_dollar_toggle(inputs, res)
    render_risk_verdict(depletion_prob, index_return_pct, _mc_std_pct, flat_b_wins=not simulation.ran_short(flat_final))

    st.space("small")

    m1, m2, m3 = st.columns(3)
    with m1:
        _n_out = round(depletion_prob * len(final_balances))
        st.metric(
            label="Futures where the money ran out",
            value=f"{_n_out:,} out of {len(final_balances):,}",
            delta=None,
            help="Out of the 1,000 possible futures, how many left your own account empty before the end of your retirement. The pension can never run out; it pays until you die.",
        )
    with m2:
        st.metric(
            label="Typical (middle) ending balance",
            value=f"${median_final:,.0f}",
            help="Line up all 1,000 futures from worst to best and pick the one in the middle. Half of the futures end with less than this, and half end with more.",
        )
    with m3:
        st.metric(
            label="Steady-return ending balance",
            value=f"${max(flat_final, 0):,.0f}",
            help="What page 1 says is left at the end, when the market grows by the same amount every year. Compare it with the typical result to the left; the order of returns can change how many payments the account covers.",
        )

    st.subheader("Why ups and downs matter")
    st.markdown("**Here is the whole idea in one example:**")
    render_html("""
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
Suppose you have &#36;1,000 and take out &#36;100 at the end of each year. If the market goes <strong>up 20% and then down 10%</strong>, you end with &#36;890. If the same two years come in the other order, <strong>down 10% and then up 20%</strong>, you end with &#36;860. <strong>Same returns, different order, &#36;30 less</strong>, because you sold more while prices were low. Over a long retirement, a few bad years early on can empty an account years sooner. That is why an account that wins with a steady return can still run out in the real world, and why this page exists.
</div>
""")
    st.space("small")

    with st.expander("Why can this page disagree with page 1?"):
        st.markdown(f"""
Page 1 uses the same {index_return_pct:.1f}% every year. This page keeps {index_return_pct:.1f}% as a typical year but adds ups and downs.

Bad years early in retirement do lasting damage. You still have to take out money to live on, so you end up selling investments while prices are low, and that money is gone before prices recover. That is why the typical result here is usually worse than page 1, and why some futures run out.

The steady-return page shows one unchanging return. This page explores how different sequences of returns affect the same payments. Neither predicts your actual outcome.
""")

    if flat_final > 0 and median_final < flat_final:
        st.markdown(
            f"Notice that the typical outcome (**\\${median_final:,.0f}**) is smaller than the flat-rate answer (**\\${max(flat_final, 0):,.0f}**), even though both use the same {index_return_pct:.1f}% typical yearly return before inflation. Changing returns affects both account growth and the impact of withdrawals, so the two ending balances need not match."
        )

    st.header("The range of your account across 1,000 futures")

    _show_flat = st.checkbox(
        "Compare with the steady-return line from page 1",
        value=False,
        key="mc_show_flat",
        help=f"Adds a teal line showing your account if the market grew exactly {index_return_pct:.1f}% every year. It is only a reference point; the shaded bands are this page's answer.",
    )
    chart_title(fund_chart_title(
        res, f"Your account: a steady {index_return_pct:.1f}% a year vs. 1,000 possible futures" if _show_flat
        else "Your account across 1,000 possible futures"))
    st.caption(f"Retirement starts at age {inputs['retirement_age']} (the red dashed line). Empty accounts stay at $0; unpaid income is not debt.")
    fig = build_fund_chart(inputs, res, show_ref_line=False, mc_pcts=mc["percentiles"], show_flat_line=_show_flat)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Shaded bands show where your account's balance lands across the 1,000 futures. Blue is the most likely range, "
        "red the unlucky futures, and green the lucky ones."
        + (f" The teal line is a steady {index_return_pct:.1f}% every year, as on page 1." if _show_flat else "")
        + " Chart amounts: k = thousand; M = million."
    )

    with st.expander("How to read this chart"):
        st.markdown("""
- **Bold teal line (optional)** = the steady-return answer: your own account if the market grew by the same amount every year. Turn it on with the checkbox above the chart.
- **Shaded bands** = at each age, the range your account's balance falls into across the 1,000 futures. Blue = the middle half (the most likely range). Red = the unlucky futures just below that, and green = the lucky ones just above it, which can go off the top of the chart. The very unluckiest and luckiest 5% are left off so the chart stays readable.
- **Red dashed vertical line** = the year retirement begins.
- **Horizontal gray line** = the \\$0 mark. Empty accounts stay at \\$0, unpaid payments count as failures, but paying everything and ending at exactly $0 does not.
""")

    with st.expander("How this was computed"):
        st.markdown(f"""
This page runs a **Monte Carlo simulation**, a standard technique for understanding risk by testing many randomized scenarios instead of one fixed one.

- We generated 1,000 sequences of yearly market returns. Each year's return is drawn at random so that a typical (median) year grows by your assumed {index_return_pct:.1f}%, the same compound rate the flat line uses, with the spread set by the swing slider above. Returns follow a lognormal curve, the standard textbook model for stock returns, so a year can never lose more than 100%.
- Each sequence is played through the exact same contribution and withdrawal schedule as the comparison page: same salary growth, same deposits while working, same yearly withdrawals in retirement.
- Once a future's balance hits \\$0, it stays at \\$0; you can't withdraw from an empty account.
- The same 1,000 sequences are reused every time, so results don't jump around between visits; they only change when you change an input.

One limitation: real markets have slightly fatter tails than this curve (extreme years are a bit more common than this model assumes), and returns can cluster (crashes are often followed by recoveries). This simulation is more realistic than a flat rate, but it is still a simplification.
""")

    st.page_link(st.session_state["_pages"]["comparison"], label="**← Back to Steady Yearly Return**", icon="⚖️")

    render_feedback_form("market-swings")
