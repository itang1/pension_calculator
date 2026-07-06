"""Page 2: what happens to Option B when returns swing year to year.

The comparison page assumes the market returns one flat rate every single
year. This page re-runs the same scenario 1,000 times with realistic
year-to-year swings (a Monte Carlo simulation; that term appears in the
methodology expander, not in the main copy) and reports how often Option B
runs out of money, when it happens, and what the typical outcome looks like.
"""

import numpy as np
import streamlit as st
from plotly import graph_objects as go

from common import build_fund_chart, get_monte_carlo, render_feedback_form, render_html


def render_risk_verdict(depletion_prob, current_rate_pct):
    """The page's answer: a traffic-light verdict on the ruin risk.

    The comparison page answers "on average, does Option B end with money?"
    The depletion probability answers "how often does Option B run out once
    returns vary?" Those are different questions, and a favorable flat-rate
    result can coexist with an unacceptably high chance of ruin. This banner
    turns the two numbers into a single risk-tiered recommendation, with a
    ✓/⚠/✗ status so the tier is readable without relying on color alone.
    """
    pct = depletion_prob * 100
    one_in = round(1 / depletion_prob) if depletion_prob > 0 else 0

    if depletion_prob <= 0.001:
        bg, bar, symbol = "#CCFBF1", "#0D9488", "✓"
        verdict = "Option B looks robust, not just favorable on average."
        body = (
            f"Even after accounting for realistic year-to-year market swings, "
            f"<strong>none</strong> of the 1,000 simulated futures ran out of money. "
            f"The flat-{current_rate_pct:.1f}% conclusion holds up under volatility."
        )
    elif depletion_prob <= 0.10:
        bg, bar, symbol = "#CCFBF1", "#0D9488", "✓"
        verdict = "Option B is the reasonable choice, with a small tail risk."
        body = (
            f"Only <strong>{pct:.0f}%</strong> (about 1 in {one_in}) of simulated futures "
            f"ran out of money. Option B's flat-rate advantage mostly survives real market "
            f"volatility; just keep a cash buffer for the unlucky minority of outcomes."
        )
    elif depletion_prob <= 0.25:
        bg, bar, symbol = "#FEF3C7", "#D97706", "⚠"
        verdict = "Genuine trade-off: neither option is clearly correct."
        body = (
            f"At a flat {current_rate_pct:.1f}% return Option B wins, but once volatility is "
            f"considered <strong>{pct:.0f}%</strong> of futures (about 1 in {one_in}) run out "
            f"of money. You are weighing Option B's higher <em>expected</em> outcome against "
            f"Option A's guarantee that you can never run out. If running out would be "
            f"catastrophic for you, Option A's certainty can be worth the lower expected value."
        )
    elif depletion_prob <= 0.50:
        bg, bar, symbol = "#FEE2E2", "#DC2626", "✗"
        verdict = "Lean toward Option A, despite the flat-rate headline."
        body = (
            f"The flat-{current_rate_pct:.1f}% line says Option B &ldquo;wins,&rdquo; but a "
            f"constant return is an optimistic assumption. Accounting for realistic ups and "
            f"downs, <strong>{pct:.0f}%</strong> of futures (roughly 1 in {one_in}) run out of "
            f"money before the end of retirement. A near coin-flip risk of ruin is usually not "
            f"worth the extra upside; Option A's lifetime guarantee is the safer call here."
        )
    else:
        bg, bar, symbol = "#FEE2E2", "#DC2626", "✗"
        verdict = "Option A is the safer choice."
        body = (
            f"Even though a flat {current_rate_pct:.1f}% return would favor Option B, "
            f"<strong>{pct:.0f}%</strong> of realistic market futures run out of money. When "
            f"most simulated outcomes end in ruin, the pension's guaranteed lifetime income is "
            f"clearly the more reliable choice."
        )

    render_html(f"""
<div style="background-color:{bg}; border-left:5px solid {bar}; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>{symbol} Adding volatility to the picture: {verdict}</strong><br><br>
{body}
<br><br><em>Why this can differ from the flat-rate result: the comparison page assumes the market returns exactly {current_rate_pct:.1f}% every single year. This page assumes the same {current_rate_pct:.1f}% <u>average</u> but with realistic year-to-year swings. Losses hurt compounding more than equal-sized gains help, and a few bad years early in retirement do lasting damage, so the typical outcome is worse than the flat line and a share of futures run out. The flat-rate result tells you the average-case winner; this depletion percentage tells you the risk. For a retirement decision, the risk usually matters more.</em>
</div>
""")


def render():
    inputs = st.session_state["_inputs"]
    res = st.session_state["_results"]
    index_return_pct = res["index_return_pct"]
    work_years = inputs["work_years"]
    retirement_years = inputs["retirement_years"]

    st.markdown(f"""
The comparison page assumes the market returns exactly {index_return_pct:.1f}% every year, forever. In reality, it looks more like [+18%, -4%, +25%, -2%, +11%...] with a different number every year, all over the place, even if it averages out to {index_return_pct:.1f}% over the long run.

**Does that difference matter? Enormously. Here is the whole idea in one example:**
""")

    render_html("""
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
Suppose your $1,000 earns <strong>+50% one year</strong> (now $1,500) and <strong>−50% the next</strong> (now $750). Your "average" return was 0%, but you lost a quarter of your money. <strong>Down years hurt more than up years help.</strong> And if the down years happen early in your retirement, while you're also withdrawing money, the damage is permanent. That is why a fund that wins with a steady return can still run out of money in the real world, and why this page exists.
</div>
""")

    st.markdown(f"""
The results below come from **1,000 of those sequences** (each one a different possible market history spanning your {work_years} years of working plus {retirement_years} years of retirement), showing the full range of where your portfolio might end up depending on how the market behaves. The teal line stays as the flat-rate baseline to compare against.
""")

    _mc_std_pct = st.slider(
        "Range of yearly market swings",
        min_value=0.0, max_value=30.0, value=15.0, step=0.5,
        key="mc_std",
        help=(
            "This controls how wide the range of yearly returns can be. "
            "At 15% (the historical norm for the US stock market), if your average "
            "return is 10%, most individual years will fall somewhere in the range of -5% to +25%. "
            "Drag lower to narrow the range (calmer markets). Drag higher to widen it (wilder swings)."
        ),
    )

    mc = get_monte_carlo(inputs, _mc_std_pct)
    depletion_prob = mc["depletion_prob"]
    final_balances = mc["final_balances"]
    median_final = float(np.percentile(final_balances, 50))
    flat_final = res["personal_balance"]

    render_risk_verdict(depletion_prob, index_return_pct)

    st.space("small")

    m1, m2, m3 = st.columns(3)
    with m1:
        _n_out = round(depletion_prob * 100)
        st.metric(
            label="Futures where the money ran out",
            value=(f"{_n_out} out of 100" if depletion_prob > 0 else "0 out of 1,000"),
            delta=None,
            help="Out of 1,000 simulated market futures, the share where the personal fund hit $0 before the end of your retirement. The pension can never do this; it pays until you die.",
        )
    with m2:
        st.metric(
            label="Typical (middle) ending balance",
            value=f"${median_final:,.0f}",
            help="Line up all 1,000 futures from worst to best; this is the one exactly in the middle. Half the futures end with less than this, half with more.",
        )
    with m3:
        st.metric(
            label="The flat-rate result says",
            value=f"${max(flat_final, 0):,.0f}",
            help="The ending balance from the comparison page, where the market returns the same flat rate every single year. Compare it to the typical outcome on the left; a flat rate flatters the result.",
        )

    if flat_final > 0 and median_final < flat_final:
        st.markdown(f"""
*Notice that the typical outcome (**${median_final:,.0f}**) is smaller than the flat-rate answer (**${max(flat_final, 0):,.0f}**), even though both use the same {index_return_pct:.1f}% average return. That's the +50%/−50% effect from the example above, compounded over a lifetime. A flat average always paints a rosier picture than the bumpy reality it summarizes.*
""")

    st.header("All 1,000 futures on one chart")

    fig = build_fund_chart(
        inputs, res, show_ref_line=False, mc_pcts=mc["percentiles"],
        title=(
            f"Option B Personal Fund Balance: flat {index_return_pct:.1f}%/yr line "
            f"vs. 1,000 simulated market futures"
        ),
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("How to read this chart"):
        st.markdown("""
- **Bold teal line** = the flat-rate baseline from the comparison page: the personal fund balance using the flat return rate you set in the sidebar, applied at the same rate every year.
- **Colored bands** = the range of possible Option B balances once the market stops returning the same rate every year. Red = the worst 20% of outcomes, blue = the middle 50% (most likely), green = the best 20%. The best-case band can extend past the top of the chart; the y-axis is fitted to the likely region.
- **Red dashed vertical line** = the year retirement begins.
- **Horizontal gray line** = the $0 mark. Once a simulated future hits $0, it has run out of money for good.
""")

    st.header("How the 1,000 futures ended")

    _cap = float(np.percentile(final_balances, 95))
    _clipped = np.minimum(final_balances, _cap)
    hist = go.Figure()
    hist.add_trace(go.Histogram(
        x=_clipped, nbinsx=40, marker_color="#3B82F6",
        hovertemplate="Ending balance range: $%{x:,.0f}<br>Number of futures: %{y}<extra></extra>",
    ))
    hist.update_layout(
        title=dict(
            text="<b>Ending balance at death, across all 1,000 futures</b>",
            x=0.5, xanchor="center", font=dict(size=15, color="#1e293b"),
        ),
        xaxis_title="Money left at the end of retirement ($)",
        yaxis_title="Number of futures",
        plot_bgcolor="white",
        bargap=0.05,
        margin=dict(l=40, r=20, t=50, b=60),
        showlegend=False,
    )
    if depletion_prob > 0:
        hist.add_annotation(
            x=0, y=float((final_balances <= 0).sum()),
            text=f"<b>✗ {round(depletion_prob * 1000)} futures ran out ($0)</b>",
            showarrow=True, arrowhead=2, arrowcolor="#DC2626",
            ax=60, ay=-40, font=dict(size=12, color="#DC2626"),
            bgcolor="rgba(255,255,255,0.85)", borderpad=4,
        )
    if flat_final > 0 and flat_final <= _cap:
        hist.add_vline(
            x=flat_final, line_width=2, line_dash="dash", line_color="#0D9488",
            annotation_text="flat-rate answer", annotation_position="top right",
            annotation_font_color="#0D9488",
        )
    hist.add_vline(
        x=median_final, line_width=2, line_dash="dot", line_color="#1e293b",
        annotation_text="typical outcome", annotation_position="top left",
        annotation_font_color="#1e293b",
    )
    st.plotly_chart(hist, width="stretch")
    st.caption(
        "The tallest bars show the most common outcomes. The luckiest 5% of futures "
        "extend beyond the right edge of this chart; they are cut off so the likely "
        "region stays readable."
    )

    _dep_years = mc["depletion_years"]
    _dep_years = _dep_years[_dep_years > 0]
    if len(_dep_years) > 0:
        st.header("When did the money run out?")
        st.markdown(f"""
Of the **{len(_dep_years)} futures** (out of 1,000) where the money ran out, here is *when* it happened. Running out in year {int(np.median(_dep_years))} of a {retirement_years}-year retirement is a very different problem than running out in the final year; this chart shows which one you'd be facing.
""")
        timing = go.Figure(go.Histogram(
            x=_dep_years, xbins=dict(size=1), marker_color="#DC2626",
            hovertemplate="Ran out in retirement year %{x}<br>Number of futures: %{y}<extra></extra>",
        ))
        timing.update_layout(
            title=dict(
                text="<b>Retirement year in which the fund hit $0</b>",
                x=0.5, xanchor="center", font=dict(size=15, color="#1e293b"),
            ),
            xaxis_title=f"Retirement year (out of your {retirement_years})",
            yaxis_title="Number of futures",
            xaxis=dict(range=[0.5, retirement_years + 0.5]),
            plot_bgcolor="white",
            bargap=0.05,
            margin=dict(l=40, r=20, t=50, b=60),
            showlegend=False,
        )
        st.plotly_chart(timing, width="stretch")

    with st.expander("How we computed this (for the curious)"):
        st.markdown(f"""
This page runs a **Monte Carlo simulation**, a standard technique for understanding risk by testing many randomized scenarios instead of one fixed one.

- We generate 1,000 sequences of yearly market returns. Each year's return is drawn from a bell curve centered on your assumed {index_return_pct:.1f}% average, with the spread set by the swing slider above (a yearly return can never fall below −100%).
- Each sequence is played through the exact same contribution and withdrawal schedule as the comparison page: same salary growth, same deposits while working, same yearly withdrawals in retirement.
- Once a future's balance hits $0, it stays at $0; you can't withdraw from an empty account.
- The same 1,000 sequences are reused every time, so results don't jump around between visits; they only change when you change an input.

One honest limitation: real markets have slightly fatter tails than a bell curve (extreme years are a bit more common than this model assumes), and returns can cluster (crashes are often followed by recoveries). This simulation is a big step more realistic than a flat rate, but it is still a simplification.
""")

    st.page_link(st.session_state["_pages"]["comparison"], label="**← Back to the comparison**", icon="⚖️")

    render_feedback_form("market-swings")
