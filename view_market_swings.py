"""Page 2: what happens to Option B when returns swing year to year.

The comparison page assumes the market returns one flat rate every single
year. This page re-runs the same scenario 1,000 times with realistic
year-to-year swings (a Monte Carlo simulation — that term appears in the
methodology expander, not in the main copy) and reports how often Option B
runs out of money.
"""

import streamlit as st

from common import build_fund_chart, get_monte_carlo, render_feedback_form, render_html


def render_mc_risk_note(depletion_prob, current_rate_pct):
    """Reconcile the flat-rate winner banner with the Monte Carlo ruin risk.

    The banner answers "on average, does Option B end with money?" The depletion
    probability answers "how often does Option B run out once returns vary?"
    Those are different questions, and a favorable flat-rate result can coexist
    with an unacceptably high chance of ruin. This note turns the two numbers
    into a single risk-tiered recommendation.
    """
    pct = depletion_prob * 100
    one_in = round(1 / depletion_prob) if depletion_prob > 0 else 0

    if depletion_prob <= 0.001:
        bg, bar = "#CCFBF1", "#0D9488"
        verdict = "Option B looks robust, not just favorable on average."
        body = (
            f"Even after accounting for realistic year-to-year market swings, "
            f"<strong>none</strong> of the 1,000 simulated futures ran out of money. "
            f"The flat-{current_rate_pct:.1f}% conclusion holds up under volatility."
        )
    elif depletion_prob <= 0.10:
        bg, bar = "#CCFBF1", "#0D9488"
        verdict = "Option B is the reasonable choice, with a small tail risk."
        body = (
            f"Only <strong>{pct:.0f}%</strong> (about 1 in {one_in}) of simulated futures "
            f"ran out of money. Option B's flat-rate advantage mostly survives real market "
            f"volatility — just keep a cash buffer for the unlucky minority of outcomes."
        )
    elif depletion_prob <= 0.25:
        bg, bar = "#FEF3C7", "#D97706"
        verdict = "Genuine trade-off — neither option is clearly correct."
        body = (
            f"At a flat {current_rate_pct:.1f}% return Option B wins, but once volatility is "
            f"considered <strong>{pct:.0f}%</strong> of futures (about 1 in {one_in}) run out "
            f"of money. You are weighing Option B's higher <em>expected</em> outcome against "
            f"Option A's guarantee that you can never run out. If running out would be "
            f"catastrophic for you, Option A's certainty can be worth the lower expected value."
        )
    elif depletion_prob <= 0.50:
        bg, bar = "#FEE2E2", "#DC2626"
        verdict = "Lean toward Option A, despite the flat-rate headline."
        body = (
            f"The flat-{current_rate_pct:.1f}% line says Option B &ldquo;wins,&rdquo; but a "
            f"constant return is an optimistic assumption. Accounting for realistic ups and "
            f"downs, <strong>{pct:.0f}%</strong> of futures (roughly 1 in {one_in}) run out of "
            f"money before the end of retirement. A near coin-flip risk of ruin is usually not "
            f"worth the extra upside — Option A's lifetime guarantee is the safer call here."
        )
    else:
        bg, bar = "#FEE2E2", "#DC2626"
        verdict = "Option A is the safer choice."
        body = (
            f"Even though a flat {current_rate_pct:.1f}% return would favor Option B, "
            f"<strong>{pct:.0f}%</strong> of realistic market futures run out of money. When "
            f"most simulated outcomes end in ruin, the pension's guaranteed lifetime income is "
            f"clearly the more reliable choice."
        )

    render_html(f"""
<div style="background-color:{bg}; border-left:5px solid {bar}; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b; margin-top:0.6rem;">
<strong>Adding volatility to the picture: {verdict}</strong><br><br>
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

This page runs your exact scenario through **1,000 different possible versions of the future** (each one a different possible market history spanning your {work_years} years of working plus {retirement_years} years of retirement) and shows the full range of where your personal fund might end up depending on how the market behaves.
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
- **Bold teal line** = the flat-rate baseline from the comparison page: the same return every single year.
- **Colored bands** = the range of possible Option B balances once the market stops returning the same rate every year. Red = the worst 20% of outcomes, blue = the middle 50% (most likely), green = the best 20%. The best-case band can extend past the top of the chart; the y-axis is fitted to the likely region.
- **Red dashed vertical line** = the year retirement begins.
- **Horizontal gray line** = the $0 mark. Once a simulated future hits $0, it has run out of money for good.
""")

    render_mc_risk_note(mc["depletion_prob"], index_return_pct)

    st.page_link(st.session_state["_pages"]["comparison"], label="**← Back to the flat-rate comparison**", icon="⚖️")

    render_feedback_form()
