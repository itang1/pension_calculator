"""Page 1: the flat-rate comparison.

Everything on this page speaks one language: the market returns the same
flat rate every single year. What happens when returns swing year to year
lives on its own page (view_market_swings.py), so readers never have to hold
both framings at once.
"""

import streamlit as st

from common import (
    build_fund_chart,
    get_monte_carlo,
    queue_preset,
    render_breakdown_table,
    render_feedback_form,
    render_html,
)


def render_result_banner(personal_balance, retirement_years, depletion_year,
                         breakeven_rate, current_rate_pct):
    """The page's answer, before any chart or table."""
    rate_buffer = current_rate_pct - breakeven_rate
    _mc_pointer = 'To see how a realistic sequence of ups and downs could change this outcome, visit the "What If the Market Has Bad Years?" page.'
    if personal_balance > 0:
        render_html(f"""
<div style="background-color:#CCFBF1; border-left:5px solid #0D9488; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>✓ Assuming a flat {current_rate_pct:.1f}% return every single year, Option B (personal fund) comes out ahead.</strong><br><br>
After {int(retirement_years)} years of retirement, Option B would still have <strong>${personal_balance:,.0f}</strong> remaining for you to keep (donate, pass on, etc.), on top of having paid out the same income as Option A every single year. Option A leaves nothing at death (besides potential survivor benefits, if applicable).
<br><br><em>You are {rate_buffer:.1f} percentage points above the {breakeven_rate:.1f}% break-even return rate, which means that the market would have to average below {breakeven_rate:.1f}% every year for Option A to win.</em>
<br><br><em>Note: this result assumes the market returns exactly {current_rate_pct:.1f}% every year without fail. Real markets have good years and bad years. {_mc_pointer}</em>
</div>
""")
    else:
        render_html(f"""
<div style="background-color:#FEF3C7; border-left:5px solid #D97706; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>✗ Assuming a flat {current_rate_pct:.1f}% return every single year, Option A (pension) comes out ahead.</strong><br><br>
Before your {int(retirement_years)}-year retirement was over, Option B would have run out of money in retirement year {depletion_year}, leaving {int(retirement_years) - depletion_year} years with no money in the account. At a flat {current_rate_pct:.1f}% return, the investment growth on Option B cannot keep up with {int(retirement_years)} years of withdrawals, so Option A's guarantee that it pays until you die is the more reliable choice here.
<br><br><em>Option B would need the market to average at least {breakeven_rate:.1f}% every year to last your full retirement. You entered {current_rate_pct:.1f}%.</em>
<br><br><em>Note: this result assumes the market returns exactly {current_rate_pct:.1f}% every year without fail. Real markets have good years and bad years. {_mc_pointer}</em>
</div>
""")


def render_risk_teaser(inputs, current_rate_pct):
    """One honest sentence about volatility risk, phrased as a frequency.

    The full analysis lives on the market-swings page; this callout makes sure
    the risk signal itself is never more than one glance away from the
    flat-rate verdict. Uses the same volatility the user last set over there
    (or the 15% historical default), so the two pages always agree.
    """
    mc = get_monte_carlo(inputs, st.session_state.get("mc_std", 15.0))
    prob = mc["depletion_prob"]
    if prob <= 0:
        render_html("""
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.6rem 1.2rem; border-radius:0.5rem; color:#1e293b; margin-top:0.6rem;">
<strong>Reality check:</strong> the market never returns the same number every year. So we also tested this exact scenario against 1,000 realistic market histories, with good years and bad years — and the money never ran out in any of them. This result looks sturdy.
</div>
""")
    else:
        pct = prob * 100
        if pct < 0.5:
            freq = "fewer than 1 out of every 100"
        else:
            freq = f"about {pct:.0f} out of every 100"
        render_html(f"""
<div style="background-color:#FEF3C7; border-left:5px solid #D97706; padding:0.6rem 1.2rem; border-radius:0.5rem; color:#1e293b; margin-top:0.6rem;">
<strong>⚠ Reality check:</strong> when we test this exact scenario against 1,000 realistic market histories — same {current_rate_pct:.1f}% average, but with good years and bad years — the money runs out early in <strong>{freq}</strong> of them.
</div>
""")
    st.page_link(
        st.session_state["_pages"]["market"],
        label="**See what happens when the market has good years and bad years →**",
        icon="🎢",
    )


def render():
    inputs = st.session_state["_inputs"]
    res = st.session_state["_results"]

    work_years = inputs["work_years"]
    retirement_years = inputs["retirement_years"]
    promotion_years = inputs["promotion_years"]
    pension_contribution_rate = inputs["pension_contribution_rate"]

    personal_fund_values = res["personal_fund_values"]
    yearly_data = res["yearly_data"]
    personal_balance = res["personal_balance"]
    index_return_pct = res["index_return_pct"]
    cola_pct = res["cola_pct"]
    step_pct = res["step_pct"]
    promotion_pct = res["promotion_pct"]

    st.markdown("""
Many public employees (such as teachers, law enforcement officers, and civil servants) are required to contribute part of each paycheck to a pension plan (e.g. a flat 10%). In return, the pension pays a guaranteed annual benefit in retirement for life, regardless of market performance.

In this calculator, we ask the question: **Instead of participating in the pension program, if an employee had the alternative option to invest that same money into their own personal retirement account, which option would produce better outcomes for them?**
""")

    render_html(
        """
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<em>&larr; On the left sidebar, enter your own assumptions about salary, contribution rate, investment return, and retirement timeline to see how the two options compare.</em>
</div>
"""
    )

    st.space("small")

    with st.expander("Explanation of the Two Options"):
        col_a, col_b = st.columns(2)
        with col_a:
            render_html("""
<div style="background-color:#FEF3C7; border-left:5px solid #D97706; padding:1rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Option A: Traditional Pension</strong><br><br>
Each year, a fixed percentage of your paycheck (e.g. 10%) is automatically deducted and funneled directly into your organization's pension system. The funds are then managed by professional fund managers who ensure its long-term stability and growth. In return, once you retire, the pension program will pay you a guaranteed annual payment for the rest of your life, regardless of broad market performance. (The specific amount will depend on your salary, years of service, and the pension formula used by your organization.)
</div>
""")
        with col_b:
            render_html("""
<div style="background-color:#CCFBF1; border-left:5px solid #0D9488; padding:1rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Option B: Personal Retirement Account</strong><br><br>
Instead of contributing to the pension, imagine that you deposit that same amount (e.g. 10%) each year into your own personal investment account. You have total control over how to invest the funds, and the balance will grow with market returns depending on your investment choices. Imagine that in retirement, you choose to withdraw the same annual amount that the pension would have paid. Additionally, any remaining balance in your account at the end of your life is yours to keep or donate as well.
</div>
""")

    render_result_banner(
        personal_balance, retirement_years, res["depletion_year"],
        res["breakeven_rate"], index_return_pct,
    )
    render_risk_teaser(inputs, index_return_pct)

    st.space("small")

    st.header("Pension vs. Personal Retirement Fund Over Time")

    with st.expander("How to read this chart"):
        st.markdown("""
Both options pay you the **same income every year in retirement**. The comparison comes down to one question: **does the Personal Fund (Option B) run out of money before you die?**

- **Bold teal line (Option B)** = the personal fund balance using the flat return rate you set in the sidebar, applied at the same rate every year. If it stays above zero through all retirement years, Option B wins. If it hits zero, Option A wins.
- **Purple line (optional)** = how much money is paid out each year. Option A pays this to you as a pension; Option B withdraws the same amount from your personal fund. Toggle it on/off with the checkbox above the chart.
- **"Working Years" and "Retirement Years" labels** mark the two phases of the chart.
- **Red dashed vertical line** = the year retirement begins.
- **Horizontal gray line** = the $0 mark. If the teal line crosses below it, Option B has run out of money.

*Wondering what happens when the market doesn't return the same rate every year? That's the whole subject of the "What If the Market Has Bad Years?" page.*
""")

    _show_ref_line = st.checkbox(
        "Show annual payout reference line",
        value=False,
        help=(
            "Adds a purple line showing how much money changes hands each year. "
            "In retirement, Option A sends you this amount as your pension check. "
            "Option B takes this exact same amount out of your personal fund. "
            "It is the same number for both options every year. "
            "This line just lets you see what that dollar amount looks like on the chart."
        ),
    )

    fig = build_fund_chart(inputs, res, _show_ref_line, verdict_annotation=True)
    st.plotly_chart(fig, width="stretch")

    st.space("small")

    _current_rate_pct = index_return_pct
    _rate_buffer = _current_rate_pct - res["breakeven_rate"]
    _years_covered = res["years_covered"]
    _depletion_year = res["depletion_year"]
    pension_contribution_total = res["pension_contribution_total"]
    pension_redeemed_total = res["pension_redeemed_total"]

    st.markdown(
        "*Reminder: in this comparison, every dollar the pension pays is also a dollar withdrawn from the personal fund. The metrics below mirror each other on both sides.*"
    )

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.metric(
            label="Pension Contributed",
            value=f"${pension_contribution_total:,.0f}",
            help="The total amount automatically deducted from your paychecks and paid into the pension system over your working years. The personal fund deposits this same amount."
        )
    with mc2:
        st.metric(
            label="Pension Received",
            value=f"${pension_redeemed_total:,.0f}",
            delta=f"${pension_redeemed_total - pension_contribution_total:,.0f} net",
            help="The total pension income paid out over all retirement years, including annual COLA increases. The personal fund withdraws this same amount. The delta shows how much more you received than you put in."
        )
    with mc3:
        st.metric(
            label="Personal Fund at Retirement",
            value=f"${personal_fund_values[work_years]:,.0f}",
            help="The balance of your hypothetical personal investment account on the day you retire, after years of contributions and market growth."
        )

    mc4, mc5, mc6 = st.columns(3)
    with mc4:
        if personal_balance > 0:
            st.metric(
                label="Final Personal Fund Balance at Death",
                value=f"${personal_balance:,.0f}",
                delta="Did not run out ✓",
                help="The personal fund still has money left after paying out the same income as the pension for every retirement year. This is money you would still own."
            )
        else:
            st.metric(
                label="Final Personal Fund Balance at Death",
                value=f"${personal_balance:,.0f}",
                delta="Ran out before death ✗",
                delta_color="inverse",
                help="The personal fund was depleted before your retirement years were up. The pension would have continued paying regardless."
            )
    with mc5:
        st.metric(
            label="Break-even Return Rate",
            value=f"{res['breakeven_rate']:.1f}%",
            delta=f"{_rate_buffer:+.1f}pp vs. your {_current_rate_pct:.1f}% assumption",
            delta_color="normal",
            help="The minimum that the market needs to return in order for your personal fund to survive your full retirement period. Compare this to your Average Index Returns Rate input.",
        )
    with mc6:
        st.metric(
            label="Years Personal Fund Covers",
            value=f"{_years_covered} / {retirement_years} yrs",
            delta="Full retirement covered ✓" if _depletion_year is None else f"Ran out {retirement_years - _years_covered} yrs early ✗",
            delta_color="normal" if _depletion_year is None else "inverse",
            help="How many retirement years Option B (personal fund) can sustain the same annual withdrawal as the pension, out of your total retirement period.",
        )

    st.markdown("""
**What you leave behind at your death:**
- With **Option B (personal fund)**, whatever the teal line shows at the end of retirement is money you still own (to donate, pass on, etc.)
- With **Option A (pension)**, payments stop when you die (unless you elected a survivor benefit, which is a reduced annual payment to a spouse or dependent after your death). This calculator does not model survivor benefits.
""")

    with st.expander("Limitations & Assumptions"):
        st.markdown("""
This calculator is an educational tool, not a comprehensive financial model. Keep these caveats in mind when reading the results:

**The return rate is the single biggest factor.** A 1% difference in long-term returns shifts the outcome dramatically between Option A and Option B. The break-even rate in the results shows the minimum return Option B needs to survive your full retirement.

**Constant inputs.** The investment return, COLA, and step increase you enter are treated as fixed values applied every year. Real markets and salary schedules fluctuate, and a few bad return years early in retirement hurt far more than a steady average suggests. The *What If the Market Has Bad Years?* page simulates this for the return rate; COLA and step increases remain flat.

**Both options pay the same annual income.** This is not a comparison about how much you receive each year. The question is whether Option B has money left over after covering all those payments through retirement. The same COLA rate is applied to both the Option A pension payment and the Option B withdrawal amount; in practice they can differ.

**Equal tax treatment for both options.** The contribution rate is applied to the personal account on the same pre-tax basis as the pension. This is fine if you have room in a 457(b) plan (a tax-advantaged account available to government employees, similar to a 401k), which has its own contribution limit separate from your pension. But if you have no tax-advantaged space available, the personal account is actually disadvantaged in a way that is not factored in here.

**Vesting matters.** If you leave before your pension vests, you may receive little or nothing. This calculator assumes you work your full stated career and collect the full benefit. Survivor and disability benefits are not modeled.

**Annual, end-of-period timing.** All contributions, deposits, and withdrawals are modeled as single lump sums at the end of each year rather than spread across pay periods. See the *Timing Assumptions* note on the sidebar for the exact ordering used. Contributions and withdrawals follow your inputs exactly with no irregular saving or mid-year deviations.

*Real retirement decisions should involve a licensed financial planner and tax professional who can account for your full situation.*
""")

    st.divider()
    st.header("Year-Over-Year Breakdown")

    st.markdown("""
Each row is one year. The left table tracks **Option A (pension)**, while the right tracks **Option B (personal fund)**. They use the same dollar amounts each year so the comparison is apples-to-apples. The bold **Total** row at the bottom of each table ties back to the summary metrics above.
""")

    with st.expander("Working Years"):
        st.markdown("""
During your working years, a fixed percentage of your salary is contributed annually. Your salary grows each year from Cost of Living Adjustments (COLA), step increases, and any promotions.
""")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Option A: Pension**")
            st.markdown(f"""
Each year, {pension_contribution_rate*100:.0f}% of your salary is deducted and paid into the pension. The **Contribution** column shows that deduction. The **Total Contributed** column is a running sum of all contributions to date.

Salary grows each year by your COLA ({cola_pct:.1f}%), plus a step increase ({step_pct:.1f}%) in your first 4 years, plus a {promotion_pct:.0f}% bump in any promotion years ({str(promotion_years).strip("[]") if promotion_years else "none entered"}). Year 1 is a special case: it averages your Step 1 and Step 2 salaries, since the Step 1→2 raise happens 6 months in.
""")
        with col2:
            st.markdown("**Option B: Personal Fund**")
            st.markdown(f"""
Instead of paying into the pension, imagine depositing that same amount each year into your own investment account. The column headers show the formula: the **Start Balance** earns **+ Returns** (investment growth at {index_return_pct:.1f}%/year), then the **+ Deposit** (same as the pension contribution) is added, producing the **= Balance** at year-end.

Returns are calculated on the balance at the *start* of the year, before that year's deposit is added.
""")
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                render_breakdown_table(
                    yearly_data[["Year", "Salary", "Pension Contribution", "Pension Contribution Total"]],
                    "W",
                    {"Pension Contribution": "Contribution", "Pension Contribution Total": "Total Contributed"},
                ),
                hide_index=True,
            )
        with col2:
            st.dataframe(
                render_breakdown_table(
                    yearly_data[["Year", "Start Balance", "Market Returns", "Pension Contribution", "Balance"]],
                    "W",
                    {"Market Returns": "+ Returns", "Pension Contribution": "+ Deposit", "Balance": "= Balance"},
                    balance_col="= Balance",
                ),
                hide_index=True,
            )

    with st.expander("Retirement Years"):
        st.markdown("""
Once you retire, contributions stop. The pension begins paying you a fixed annual allowance that grows each year with COLA. The personal fund is drawn down by that same amount each year, but continues earning investment returns on whatever balance remains. If the **= Balance** ever turns red (negative), the personal fund has run out. The year it first goes red is the year that you will wish you had chosen the pension option, since the pension provides a lifetime guarantee.
""")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Option A: Pension**")
            st.markdown(f"""
The pension pays a set annual amount, growing by {cola_pct:.1f}% each year (COLA). **Pension Received** is that year's payment. **Total Received** is the running sum of all payments to date.
""")
        with col2:
            st.markdown("**Option B: Personal Fund**")
            st.markdown(f"""
Each year, you withdraw the same dollar amount as the pension would have paid. The column headers show the formula: the **Start Balance** earns **+ Returns** ({index_return_pct:.1f}%/year), then the **− Withdrawal** is subtracted, leaving **= Balance**. If returns exceed the withdrawal, the balance grows. If not, it shrinks.
""")
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                render_breakdown_table(
                    yearly_data[["Year", "Pension Redeemed", "Pension Redeemed Total"]],
                    "R",
                    {"Pension Redeemed": "Pension Received", "Pension Redeemed Total": "Total Received"},
                ),
                hide_index=True,
            )
        with col2:
            st.dataframe(
                render_breakdown_table(
                    yearly_data[["Year", "Start Balance", "Market Returns", "Pension Redeemed", "Balance"]],
                    "R",
                    {"Start Balance": "Start Balance",
                     "Market Returns": "+ Returns",
                     "Pension Redeemed": "− Withdrawal",
                     "Balance": "= Balance"},
                    balance_col="= Balance",
                ),
                hide_index=True,
            )

    st.divider()
    st.header("Case Studies")

    st.markdown("""
The two examples below show one scenario where each option wins. To see the full charts and tables for either, click its **Try this scenario** button (or copy the listed settings into the calculator above).
""")

    with st.expander("Case Study A: Personal Fund Wins"):
        st.markdown("""
**Settings:** Starting wage \\$120,000 · Step increase 5.5% · COLA 3% · Promotions at years 10 and 20 (8% each) · Pension contribution rate 10% · Index returns 7% · Work years 30 · Retirement years 30 · First-year pension allowance \\$70,458
""")
        if st.button("Try Alice's scenario in the calculator", key="load_alice", icon="▶️"):
            queue_preset("alice")
        st.markdown("""
---

Alice is a public school administrator who starts at \\$120,000. Across a 30-year career, her salary climbs through step increases, COLA adjustments, and two promotions. Every year, 10% of it goes into the pension.

**The pension:** By the time Alice retires, she has paid about **\\$770,000** into the pension. In return, she gets an allowance that starts around \\$70,458 a year and rises 3% annually. Add up 30 years of those payments and she collects roughly **\\$3.35 million**.

**The personal fund:** Now suppose she had put those same contributions into an account earning 7% a year instead. By retirement it would hold about **\\$2 million**. She then withdraws the same amount the pension would have paid each year. Since 7% growth outpaces what she takes out, the balance keeps climbing through retirement and finishes above **\\$6 million**.

**Verdict:** The personal fund wins, and it is worth being clear about why. Both options pay Alice the exact same income every year she is retired. The pension never hands her an extra dollar. The whole difference is what is left at the end. The personal fund still holds over \\$6 million that she owns and can pass to her family, while the pension leaves nothing once she dies.

This is also the scenario people misread most often. They see "\\$3.35 million in pension income" and assume the pension came out ahead, but that number is just the running total of Alice's annual payments; keep in mind that the personal fund paid out that same amount! The \\$6 million is *extra* that she gets to keep (donate, pass on, etc.), on top of the \\$3.35 million that she already withdrew and spent during her life.
""")

    with st.expander("Case Study B: Pension Wins"):
        st.markdown("""
**Settings:** Starting wage \\$65,000 · Step increase 5.5% · COLA 3% · No promotions · Pension contribution rate 10% · Index returns 5% · Work years 20 · Retirement years 40 · First-year pension allowance \\$27,000
""")
        if st.button("Try Bob's scenario in the calculator", key="load_bob", icon="▶️"):
            queue_preset("bob")
        st.markdown("""
---

Bob is a civil servant who starts at \\$65,000 and works a steady 20 years with no promotions. He retires fairly early and then spends 40 years in retirement before he dies. Over that lifetime the market returns a modest 5% a year.

**The pension:** During his 20 working years, Bob pays about **\\$212,000** into the pension. In retirement he collects around \\$27,000 the first year, rising 3% annually. Stretched over 40 years, that comes to roughly **\\$2 million**, almost 10 times what he put in.

**The personal fund:** Those same contributions, growing at 5% a year, would leave Bob with about **\\$332,000** at retirement. Once he starts pulling out \\$27,000 a year (rising 3% annually), the growth cannot keep up with the withdrawals. The account runs dry in **about 15 years**, leaving nothing for his final 25 years.

**Verdict:** The pension wins because Bob outlives his savings. At 5% returns, a \\$332,000 balance just cannot fund 40 years of withdrawals. What carries him through is the pension's promise to keep paying for as long as he lives. Without it, he runs out of money in his early 70s.

The pension option tends to come out ahead when returns are low, retirement is long, or the personal fund didn't have enough working years to grow.
""")

    render_feedback_form("comparison")
