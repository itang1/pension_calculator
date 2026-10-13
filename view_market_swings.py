"""Page 2: what happens to your account when returns swing year to year.

The comparison page assumes the market returns one flat rate every single
year. This page re-runs the same scenario 1,000 times with realistic
year-to-year swings (a Monte Carlo simulation; that term appears in the
methodology expander, not in the main copy) and reports how often your account
runs out of money, when it happens, and what the typical outcome looks like.
"""

import numpy as np
import streamlit as st

import simulation
from plotly import graph_objects as go

from common import (
    build_fund_chart,
    chart_title,
    fund_chart_title,
    deflate_mc,
    inputs_summary_html,
    out_of_100,
    dollars_note,
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
    """Describe modeled outcomes without recommending a personal choice."""
    n = out_of_100(depletion_prob)
    bg, bar = ("#CCFBF1", "#0D9488") if depletion_prob <= 0.10 else ("#E0E7FF", "#4F46E5")
    symbol = ""
    if std_pct == 0:
        verdict = "With market swings at 0%, every simulation repeats the steady-return calculation."
        body = (
            f"Each year returns exactly {current_rate_pct:.1f}% before inflation. "
            + ("Your account cannot cover every payment in any of the 1,000 simulations." if depletion_prob else
               "Your account covers every payment in all 1,000 simulations.")
        )
    elif depletion_prob == 0:
        verdict = "Your account covers every payment in all 1,000 simulations."
        body = "None of these simulations ran short. This does not guarantee the same result in real markets."
    else:
        verdict = f"Your account runs short in {n} out of 100 simulated scenarios."
        body = (
            "In those scenarios, the account cannot cover at least one full pension payment. "
            "The modeled pension continues paying. These are results under your assumptions, "
            "not a prediction of your personal odds."
        )
    render_html(f"""
<div style="background-color:{bg}; border-left:5px solid {bar}; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
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
The steady-return page assumes investments grow by exactly {index_return_pct:.1f}% every single year before inflation. Real markets don't work that way. Some years are way up and some are way down (say +18%, −4%, +25%, −12%), even if a typical year is still about {index_return_pct:.1f}%.

**So this page asks: with simulated ups and downs, how often does your account run short?**

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

    chart_title(fund_chart_title(
        res, f"Your account: a steady {index_return_pct:.1f}% a year vs. 1,000 possible futures"))
    st.caption(f"Retirement starts at age {inputs['retirement_age']} (the red dashed line). Empty accounts stay at $0; unpaid income is not debt.")
    fig = build_fund_chart(inputs, res, show_ref_line=False, mc_pcts=mc["percentiles"])
    st.plotly_chart(fig, width="stretch")
    st.caption("Chart amounts: k = thousand; M = million.")

    with st.expander("How to read this chart"):
        st.markdown("""
- **Bold teal line** = the steady-return answer: your own account if the market grew by the same amount every year.
- **Shaded bands** = at each age, the range your account's balance falls into across the 1,000 futures. Blue = the middle half (the most likely range). Red = the unlucky futures just below that, and green = the lucky ones just above it, which can go off the top of the chart. The very unluckiest and luckiest 5% are left off so the chart stays readable.
- **Red dashed vertical line** = the year retirement begins.
- **Horizontal gray line** = the \\$0 mark. Empty accounts stay at \\$0, unpaid payments count as failures, but paying everything and ending at exactly $0 does not.
""")

    st.header("How the 1,000 futures ended")

    # "Ran out" comes from the engine (a payment went unpaid), so a future
    # that pays everything and ends at exactly $0 is not counted as a failure.
    ran_out_mask = mc["depletion_years"] > 0
    ran_out_count = int(ran_out_mask.sum())
    survivors = final_balances[~ran_out_mask]
    _cap = float(np.percentile(final_balances, 95))
    hist = go.Figure()
    _w = 1.0
    if len(survivors) > 0 and _cap > 0:
        shown = survivors[survivors <= _cap]
        counts, edges = np.histogram(shown, bins=30, range=(0.0, _cap))
        _w = _cap / 30
        centers = (edges[:-1] + edges[1:]) / 2
        hist.add_trace(go.Bar(
            x=centers, y=counts, width=_w * 0.92, marker_color="#3B82F6",
            hovertemplate="Ending balance near $%{x:,.0f}<br>Number of futures: %{y}<extra></extra>",
        ))
    elif len(survivors) > 0:
        _w = max(float(survivors.max()) / 30, 1.0)
    if ran_out_count > 0:
        hist.add_trace(go.Bar(
            x=[-_w / 2], y=[ran_out_count], width=_w * 0.92, marker_color="#DC2626",
            hovertemplate="Ran out of money ($0)<br>Number of futures: %{y}<extra></extra>",
        ))
    hist.update_layout(
        xaxis_title="Money left at the end of retirement ($)",
        yaxis_title="Number of futures",
        xaxis=dict(tickformat=".2s", separatethousands=True),
        plot_bgcolor="white",
        barmode="overlay",
        margin=dict(l=40, r=20, t=90, b=60),
        showlegend=False,
    )
    if 0 < flat_final <= _cap:
        hist.add_vline(x=flat_final, line_width=2, line_dash="dash", line_color="#0D9488")
    if median_final > 0:
        hist.add_vline(x=median_final, line_width=2, line_dash="dot", line_color="#1e293b")
    st.caption(f"{ran_out_count:,} scenarios could not cover all payments. Dashed teal: steady-return result. Dotted gray: middle result.")
    chart_title(f"Ending balance, across all 1,000 futures{dollars_note(res)}")
    st.plotly_chart(hist, width="stretch")
    st.caption(
        "The tallest bars show the most common outcomes. The red bar left of $0 counts "
        "the futures that ran out of money. The luckiest 5% of futures extend beyond "
        "the right edge of this chart; they are left out so the likely region stays readable."
    )

    _dep_years = mc["depletion_years"]
    _dep_years = _dep_years[_dep_years > 0]
    if len(_dep_years) > 0:
        st.header("When did the money run out?")
        st.markdown(f"""
Of the **{len(_dep_years)} futures** (out of 1,000) where the money ran out, here is *when* it happened. Running out in year {int(np.median(_dep_years))} of a {retirement_years}-year retirement is a very different problem than running out in the final year; this chart shows which one you'd be facing.
""")
        # Plotted by age (the age you reach by the end of the year the money
        # ran out), matching the age axis on the fund chart above.
        _ret_age = inputs["retirement_age"]
        timing = go.Figure(go.Histogram(
            x=_dep_years + _ret_age, xbins=dict(size=1), marker_color="#DC2626",
            hovertemplate="Ran out by age %{x}<br>Number of futures: %{y}<extra></extra>",
        ))
        timing.update_layout(
            xaxis_title=f"Your age (retirement runs from {_ret_age} to {_ret_age + retirement_years})",
            yaxis_title="Number of futures",
            xaxis=dict(range=[_ret_age + 0.5, _ret_age + retirement_years + 0.5]),
            plot_bgcolor="white",
            bargap=0.05,
            margin=dict(l=40, r=20, t=20, b=60),
            showlegend=False,
        )
        chart_title("Age by which the account hit $0")
        st.plotly_chart(timing, width="stretch")

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
