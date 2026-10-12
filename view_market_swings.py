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
    deflate_mc,
    inputs_summary_html,
    out_of_100,
    dollars_note,
    get_monte_carlo,
    render_feedback_form,
    render_html,
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

    if tier == "none":
        bg, bar, symbol = "#CCFBF1", "#0D9488", "✓"
        verdict = "Your account holds up, even in bad markets."
        body = (
            "In all 1,000 possible futures, your account never ran out of money. "
            "The answer from page 1 holds up."
        )
    elif tier == "small":
        bg, bar, symbol = "#CCFBF1", "#0D9488", "✓"
        verdict = "Your account is a reasonable choice, with a small risk."
        body = (
            f"Your account ran out of money in <strong>{n} out of 100</strong> possible futures. "
            f"Usually it works out. If you choose it, keep some savings aside in case you land "
            f"in one of the unlucky ones."
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
        verdict = "Lean toward the pension, even though page 1 picked your own account."
        body = (
            f"Page 1 assumed a smooth {r} every year. With real ups and downs, your account ran out "
            f"of money in <strong>{n} out of 100</strong> possible futures. That is close to a coin "
            f"flip, which is too risky for most people's retirement money."
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
Page 1 pretended the stock market grows by exactly {index_return_pct:.1f}% every single year. Real markets don't work that way. Some years are way up and some are way down (say +18%, −4%, +25%, −12%), even if a typical year is still about {index_return_pct:.1f}%.

**So this page asks: with real ups and downs, how often does your account run out of money?**

To find out, we made up **1,000 possible futures** for the stock market. Each one is a different random mix of good and bad years, like rolling dice for every year of your {work_years} working years and {retirement_years} retired years. Then we ran your plan through every one of them.
""")

    _mc_std_pct = st.slider(
        "How bumpy is the market?",
        min_value=0.0, max_value=30.0, value=15.0, step=0.5, format="%.1f%%",
        key="mc_std",
        help=(
            "How far a single year can swing away from the typical year. 15% matches the U.S. "
            f"stock market's history: with a typical year of {index_return_pct:.0f}%, most years land "
            f"somewhere between about {index_return_pct - 15:.0f}% and {index_return_pct + 15:.0f}%. "
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
        render_html(f"""
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>You would get a refund, not a lifetime pension.</strong><br><br>
With real ups and downs, your own account ended up with more than the refund (about &#36;{refund:,.0f}) in
<strong>{out_of_100(wins / len(mc["balances_at_leaving"]))} out of 100</strong> possible futures. The refund grows at a
guaranteed {simulation.PLAN_REFUND_INTEREST_PCT:g}% a year, so your account has to beat that to come out ahead.
</div>
""")
        st.page_link(st.session_state["_pages"]["comparison"], label="**← Back to Base Comparison: Flat Rate**", icon="⚖️")
        render_feedback_form("market-swings")
        return

    st.header("Your Result")
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
            label="The flat-rate result says",
            value=f"${max(flat_final, 0):,.0f}",
            help="What page 1 says is left at the end, when the market grows by the same amount every year. Compare it with the typical result to the left; a smooth market makes things look better than they usually turn out.",
        )

    st.subheader("Why ups and downs matter")
    st.markdown("**Here is the whole idea in one example:**")
    render_html("""
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
Suppose your $1,000 earns <strong>+50% one year</strong> (now $1,500) and <strong>−50% the next</strong> (now $750). Your "average" return was 0%, but you lost a quarter of your money. <strong>Down years hurt more than up years help.</strong> And if the down years happen early in your retirement, while you're also withdrawing money, the damage is permanent. That is why a fund that wins with a steady return can still run out of money in the real world, and why this page exists.
</div>
""")
    st.space("small")

    with st.expander("Why can this page disagree with page 1?"):
        st.markdown(f"""
Page 1 uses the same {index_return_pct:.1f}% every year. This page keeps {index_return_pct:.1f}% as a typical year but adds ups and downs.

Bad years early in retirement do lasting damage. You still have to take out money to live on, so you end up selling investments while prices are low, and that money is gone before prices recover. That is why the typical result here is usually worse than page 1, and why some futures run out.

Page 1 tells you who wins in a smooth, average market. This page tells you the risk. For retirement money, the risk usually matters more.
""")

    if flat_final > 0 and median_final < flat_final:
        st.markdown(
            f"Notice that the typical outcome (**\\${median_final:,.0f}**) is smaller than the flat-rate answer (**\\${max(flat_final, 0):,.0f}**), even though both use the same {index_return_pct:.1f}% average return. That's the bad-years-early effect from the example above: withdrawals made after a drop lock in the loss. A flat rate usually paints a rosier picture of retirement than the bumpy reality it summarizes."
        )

    st.header("All 1,000 possible futures on one chart")

    fig = build_fund_chart(
        inputs, res, show_ref_line=False, mc_pcts=mc["percentiles"],
        title=(
            f"Your own account: a steady {index_return_pct:.1f}% a year "
            f"vs. 1,000 possible futures"
        ),
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("How to read this chart"):
        st.markdown("""
- **Bold teal line** = page 1's answer: your own account if the market grew by the same amount every year.
- **Shaded bands** = where your own account lands across the 1,000 possible futures. Blue = the middle half of futures (the most likely range). Red = the unluckiest futures. Green = the luckiest ones, which can go off the top of the chart.
- **Red dashed vertical line** = the year retirement begins.
- **Horizontal gray line** = the \\$0 mark. Once a simulated future hits \\$0, it has run out of money permanently.
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
        hist.add_annotation(
            x=-_w / 2, y=ran_out_count,
            text=f"<b>✗ {ran_out_count} futures ran out ($0)</b>",
            showarrow=True, arrowhead=2, arrowcolor="#DC2626",
            ax=80, ay=-30, font=dict(size=12, color="#DC2626"),
            bgcolor="rgba(255,255,255,0.85)", borderpad=4,
        )
    hist.update_layout(
        title=dict(
            text=f"<b>Ending balance at death, across all 1,000 futures{dollars_note(res)}</b>",
            x=0.5, xanchor="center", font=dict(size=15, color="#1e293b"),
        ),
        xaxis_title="Money left at the end of retirement ($)",
        yaxis_title="Number of futures",
        xaxis=dict(tickformat=",", separatethousands=True),
        plot_bgcolor="white",
        barmode="overlay",
        margin=dict(l=40, r=20, t=90, b=60),
        showlegend=False,
    )
    # Both markers are labelled above the plot, on different rows, so the two
    # captions never collide when the flat-rate and typical lines land close
    # together (previously "flat-rate answer" and "typical outcome" overlapped).
    if flat_final > 0 and flat_final <= _cap:
        hist.add_vline(
            x=flat_final, line_width=2, line_dash="dash", line_color="#0D9488",
            annotation_text="flat-rate answer", annotation_position="top",
            annotation_font_color="#0D9488", annotation_yshift=34,
        )
    if median_final > 0:
        hist.add_vline(
            x=median_final, line_width=2, line_dash="dot", line_color="#1e293b",
            annotation_text="typical outcome", annotation_position="top",
            annotation_font_color="#1e293b", annotation_yshift=14,
        )
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
            title=dict(
                text="<b>Age by which the fund hit $0</b>",
                x=0.5, xanchor="center", font=dict(size=15, color="#1e293b"),
            ),
            xaxis_title=f"Your age (retirement runs from {_ret_age} to {_ret_age + retirement_years})",
            yaxis_title="Number of futures",
            xaxis=dict(range=[_ret_age + 0.5, _ret_age + retirement_years + 0.5]),
            plot_bgcolor="white",
            bargap=0.05,
            margin=dict(l=40, r=20, t=50, b=60),
            showlegend=False,
        )
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

    st.page_link(st.session_state["_pages"]["comparison"], label="**← Back to Base Comparison: Flat Rate**", icon="⚖️")

    render_feedback_form("market-swings")
