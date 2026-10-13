"""Page 1: the flat-rate comparison.

Everything on this page speaks one language: the market returns the same
flat rate every single year. What happens when returns swing year to year
lives on its own page (view_market_swings.py), so readers never have to hold
both framings at once.
"""

import math

import streamlit as st

import simulation

from common import (
    CURRENT_YEAR,
    ages_for,
    build_fund_chart,
    build_rate_curve_chart,
    chart_title,
    fund_chart_title,
    rate_chart_title,
    fmt_rate,
    get_monte_carlo,
    inputs_summary_html,
    out_of_100,
    queue_preset,
    render_breakdown_table,
    render_feedback_form,
    render_html,
    render_inflation_explanation,
    account_payment_table,
    restore_previous_inputs,
)


def render_result_banner(personal_balance, retirement_years, depletion_year,
                         breakeven_rate, current_rate_pct, real_dollars=False,
                         runs_out=None):
    """The page's answer, before any chart or table.

    ``runs_out`` is page 2's count ("N" out of 100 futures), shown here so a
    reader who never opens page 2 still sees the risk behind a smooth-market win.
    """
    short = depletion_year is not None
    dollars = f" in buying power at today's ({CURRENT_YEAR}) prices" if real_dollars else " in the dollars of the final year, without adjusting for inflation"
    if short:
        title = "Your account cannot cover every pension payment in this scenario."
        following = int(retirement_years) - depletion_year
        body = (
            f"It fully covers the first {depletion_year - 1} years of the comparison. "
            f"It cannot cover the full payment in retirement year {depletion_year}. "
            + (f"The remaining {following} years are also unfunded. " if following else "")
            + "The modeled pension continues paying for the full period."
        )
        bg, bar = "#E0E7FF", "#4F46E5"
    elif personal_balance <= 0.5:
        title = "Your account covers every payment, with nothing left at the end."
        body = f"Both options cover the same income over the {int(retirement_years)} years shown."
        bg, bar = "#F1F5F9", "#64748B"
    else:
        title = "Your account covers every payment and finishes with money left."
        body = (
            f"After {int(retirement_years)} years, it has <strong>${personal_balance:,.0f}</strong>{dollars} "
            "left after covering the same income as the pension. Survivor benefits are not included."
        )
        bg, bar = "#CCFBF1", "#0D9488"
    render_html(f"""
<div style="background-color:{bg}; border-left:5px solid {bar}; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>{title}</strong><br><br>
This calculation assumes your investments grow by <strong>{current_rate_pct:.1f}% every year before inflation</strong>, with no market ups and downs.<br><br>
{body}<br><br>
The account needs a steady return of <strong>{fmt_rate(breakeven_rate)} before inflation</strong> to cover all payments under these assumptions.
</div>
""")
    if runs_out is not None:
        std = st.session_state.get("mc_std", 15.0)
        if std == 0:
            st.caption("Market swings are set to 0%, so the simulations on the second page repeat this same calculation.")
        else:
            st.caption(f"With the current market-swing setting ({std:g}%), the account runs short in {runs_out} out of 100 simulated scenarios. These are model results, not a prediction of your personal odds.")
    # st.page_link (not an HTML anchor inside the banner) so navigation stays
    # client-side and the visitor's input panel inputs survive the page switch.
    st.page_link(
        st.session_state["_pages"]["market"],
        label=(
            '*See how market ups and downs change this result →*'
        ),
        icon="🎢",
    )


def render_refund_result(inputs, res):
    """Result for someone who leaves before vesting: a refund, not a pension.

    Both the refund and your own account grow from the same deposits, so they
    are compared on the day you leave. Your own account comes out ahead only
    if it earns more than the plan's refund interest rate.
    """
    refund = res["refund"]
    account = res["account_at_leaving"]
    rate = simulation.PLAN_REFUND_INTEREST_PCT
    dollars = f" in buying power at today's ({CURRENT_YEAR}) prices" if res.get("real_dollars") else " in the dollars of the year you leave"
    if abs(account - refund) <= max(1.0, 1e-9 * refund):
        winner, color, bar = "The refund and account have the same value", "#F1F5F9", "#64748B"
    elif account > refund:
        winner, color, bar = "Your account is larger than the refund", "#CCFBF1", "#0D9488"
    else:
        winner, color, bar = "The contribution refund is larger than your account", "#E0E7FF", "#4F46E5"
    st.header("Your Result")
    render_html(f"""
<div style="background-color:{color}; border-left:5px solid {bar}; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<div style="font-size:1.4rem; font-weight:700; margin-bottom:0.6rem;">{winner}</div>
<strong>You qualify for a refund of your contributions, not a lifetime pension.</strong><br><br>
With {inputs["work_years"]} years of service you would not vest, so when you leave the plan pays back what you put in, plus {rate:g}% interest a year: about <strong>&#36;{refund:,.0f}</strong>{dollars}. Your own account, earning {res["index_return_pct"]:.1f}% a year before inflation on the same deposits, would hold about <strong>&#36;{account:,.0f}</strong>{dollars} when you leave.
<br><br><em>Because both grow from the same deposits, your own account comes out ahead only if it earns more than {rate:g}% a year. Staying at least {simulation.PLAN_VESTING_YEARS} years would earn you a lifetime pension instead of a refund.</em>
</div>
""")
    st.space("small")
    c1, c2 = st.columns(2)
    c1.metric(f"Refund When You Leave (Age {inputs['retirement_age']})", f"${refund:,.0f}",
              help=f"Your contributions plus {rate:g}% interest a year, paid back when you leave.")
    c2.metric(f"Your Account When You Leave (Age {inputs['retirement_age']})", f"${account:,.0f}",
              help="The same deposits in your own account, growing at the return you entered.")


def render():
    inputs = st.session_state["_inputs"]
    res = st.session_state["_results"]

    work_years = inputs["work_years"]
    retirement_years = inputs["retirement_years"]
    promotion_years = inputs["promotion_years"]
    pension_contribution_rate = inputs["pension_contribution_rate"]

    personal_fund_values = res["personal_fund_values"]
    personal_balance = res["personal_balance"]
    index_return_pct = res["index_return_pct"]
    cola_pct = res["cola_pct"]
    step_pct = res["step_pct"]
    promotion_pct = res["promotion_pct"]

    st.markdown("""
Many public employees, like teachers, police officers, and city workers, must put part of every paycheck (for example, 10%) into a pension. In return, the pension pays them a set amount every year after they retire, for the rest of their life, no matter what the stock market does.

This calculator asks one question: **if you could put that same money into your own retirement account instead, would the account cover the same pension payments, and would any money remain?**
""")

    render_html(
        f"""
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<em>Open the input panel above to enter your salary, ages, and pension details. Results update as you go.</em>
<br><br>{inputs_summary_html(inputs, res)}
</div>
"""
    )

    st.space("small")

    st.subheader("Explanation of the Two Options")
    col_a, col_b = st.columns(2)
    with col_a:
        render_html("""
<div style="background-color:#E0E7FF; border-left:5px solid #4F46E5; padding:1rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Option A: The Pension</strong><br><br>
Each year, a set part of your paycheck (for example, 10%) goes straight into the pension fund, where professional managers invest it. Once you retire, the pension pays you a guaranteed amount every year for the rest of your life, even if the stock market crashes. How much you get depends on your salary, your years of work, and your plan's formula.
</div>
""")
    with col_b:
        render_html("""
<div style="background-color:#CCFBF1; border-left:5px solid #0D9488; padding:1rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Option B: Your Own Account</strong><br><br>
Instead of paying into the pension, imagine putting the same amount (for example, 10%) into your own investment account each year. You choose how to invest it, and it grows or shrinks with the market. In retirement, you take out the same amount each year that the pension would have paid you. Anything left when you die is yours to pass on or give away.
</div>
""")
    st.space("small")

    render_inflation_explanation(inputs, res)

    if inputs["plan_status"] == "unvested":
        # No pension to compare: show the refund against your own account instead
        # of lifetime-income charts that do not apply.
        render_refund_result(inputs, res)
    else:
        # The verdict comes first, in its own section; the chart and metrics below explain it.
        st.header("Your Result")
        render_result_banner(
            personal_balance, retirement_years, res["depletion_year"],
            res["breakeven_rate"], index_return_pct, res.get("real_dollars", False),
            runs_out=out_of_100(get_monte_carlo(inputs, st.session_state.get("mc_std", 15.0))["depletion_prob"]),
        )

        st.space("small")

        st.header("Would Your Account Cover the Pension Payments?")

        with st.expander("How to read this chart"):
            st.markdown("""
    Both options pay you the **same income every year in retirement**. The comparison comes down to one question: **does your own account run out of money before you die?**

    - **Bold teal line (your own account)** = your account's balance using the flat return rate you set in the input panel, applied at the same rate every year. It stops at $0 when the account is empty. Any income it could not pay is shown separately below.
    - **Purple line (optional)** = how much money is paid out each year. The pension pays this to you; the same amount comes out of your own account. Toggle it on/off with the checkbox above the chart.
    - **Horizontal axis** = your age, from the year you are hired to the end of retirement. Hover over a point to see that year's numbers.
    - **"Working Years" and "Retirement Years" labels** mark the two phases of the chart.
    - **Red dashed vertical line** = the year retirement begins.
    - **Horizontal gray line** = the $0 mark. The line stays here once the account is empty. Ending at exactly $0 after paying everything is fully funded.

    *Wondering what happens when the market doesn't return the same rate every year? That's the whole subject of the "What If the Market Has Bad Years?" page.*
    """)

        _show_ref_line = st.checkbox(
            "Show the yearly pension payment",
            value=False,
            help=(
                "Adds a purple line showing how much money changes hands each year. "
                "In retirement, the pension sends you this amount as your pension check. "
                "Your own account pays out this exact same amount. "
                "It is the same number for both options every year. "
                "This line just lets you see what that dollar amount looks like on the chart."
            ),
        )

        chart_title(fund_chart_title(res))
        st.caption(
            f"Retirement starts at age {inputs['retirement_age']}. "
            + (f"The first payment the account cannot fully cover is at age {inputs['retirement_age'] + res['depletion_year']}." if res['depletion_year'] else "The account covers all payments through the ending age.")
        )
        fig = build_fund_chart(inputs, res, _show_ref_line, verdict_annotation=True)
        st.plotly_chart(fig, width="stretch")
        st.caption("Chart amounts: k = thousand; M = million.")

        if res["depletion_year"] is not None:
            st.metric("Total Income the Account Could Not Pay", f"${-personal_balance:,.0f}",
                      help="Unpaid pension-equivalent income, not money you owe. Uses the dollar display selected above.")
        st.markdown(
            "*Both options aim to pay the same income. Once the account is empty, any payments it cannot cover are counted as unpaid income.*"
        )

        st.space("small")

        _current_rate_pct = index_return_pct
        _rate_buffer = _current_rate_pct - res["breakeven_rate"]
        _years_covered = res["years_covered"]
        _depletion_year = res["depletion_year"]
        pension_contribution_total = res["pension_contribution_total"]
        pension_redeemed_total = res["pension_redeemed_total"]

        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.metric(
                label=f"Pension Contributed over {work_years} Years",
                value=f"${pension_contribution_total:,.0f}",
                help="The total amount automatically deducted from your paychecks and paid into the pension system over your working years. Your own account receives this same amount as deposits."
            )
        with mc2:
            st.metric(
                label=f"Pension Received over {retirement_years} Years",
                value=f"${pension_redeemed_total:,.0f}",
                delta=f"${pension_redeemed_total - pension_contribution_total:,.0f} net",
                help="The total pension income over all retirement years, including yearly increases. Your own account attempts to match these payments while money remains. With buying power switched on, each year's amount is adjusted to today's prices before adding them up. The difference below shows total income minus total contributions."
            )
        with mc3:
            st.metric(
                label=f"Your Account at Retirement (Age {inputs['retirement_age']})",
                value=f"${personal_fund_values[work_years]:,.0f}",
                help="The balance of your own (hypothetical) investment account on the day you retire, after years of contributions and market growth."
            )

        mc4, mc5, mc6 = st.columns(3)
        with mc4:
            if res["depletion_year"] is None:
                st.metric(
                    label=f"Your Account at the End (Age {inputs['retirement_age'] + retirement_years})",
                    value=f"${max(personal_balance, 0):,.0f}",
                    delta="Did not run out ✓",
                    delta_arrow="off",
                    help="Your own account still has money left after paying out the same income as the pension for every retirement year. This is money you would still own."
                )
            else:
                st.metric(
                    label=f"Your Account at the End (Age {inputs['retirement_age'] + retirement_years})",
                    value="$0",
                    delta="Some payments were not fully covered",
                    delta_arrow="off",
                    delta_color="inverse",
                    help=(
                        "Your own account ran dry before your retirement years were up. The pension would have continued paying regardless. "
                        f"Over the remaining years, your account would have come up ${-personal_balance:,.0f} short of the same income."
                    ),
                )
        with mc5:
            st.metric(
                label="Break-even Return Rate",
                value=fmt_rate(res["breakeven_rate"]),
                delta=(
                    f"far above your {_current_rate_pct:.1f}% assumption" if math.isinf(_rate_buffer)
                    else f"{_rate_buffer:+.1f} points vs. your {_current_rate_pct:.1f}% assumption"
                ),
                delta_color="inverse" if math.isinf(_rate_buffer) else "normal",
                help="The lowest steady yearly return, before inflation, that covers all modeled pension payments through your chosen ending age.",
            )
        with mc6:
            st.metric(
                label="Fully Funded Retirement Years",
                value=f"{_years_covered} / {retirement_years} yrs",
                delta="Full retirement covered ✓" if _depletion_year is None else f"{retirement_years - _years_covered} years include unpaid income",
                delta_arrow="off",
                delta_color="normal" if _depletion_year is None else "inverse",
                help="How many retirement years your own account can sustain the same annual withdrawal as the pension, out of your total retirement period.",
            )

        st.subheader("How the answer changes with the return rate")
        st.markdown(
            "Below the break-even return, the account cannot cover every payment. Above it, money remains. "
            "Empty accounts are shown at $0. All returns on this chart are before inflation."
        )
        st.caption(f"Dashed gray: your {index_return_pct:.1f}% assumption. Dotted teal: {fmt_rate(res['breakeven_rate'])} break-even return.")
        chart_title(rate_chart_title(res))
        st.plotly_chart(build_rate_curve_chart(inputs, res), width="stretch")
        st.caption("Chart amounts: k = thousand; M = million.")

        st.markdown("""
    **What you leave behind at your death:**
    - With **your own account**, whatever the teal line shows at the end of retirement is money you still own (to donate, pass on, etc.)
    - With **the pension**, payments stop when you die. Survivor benefits depend on your eligibility and the benefit option you choose, and are not included here; for members who qualify, they add value to the pension that this comparison leaves out.
    """)

        with st.expander("Limitations & Assumptions"):
            st.markdown("""
    This calculator is an educational tool, not a comprehensive financial model. Keep these caveats in mind when reading the results:

    **The return rate is the single biggest factor.** A 1% difference in long-term returns shifts the outcome dramatically between the pension and your own account. The break-even rate in the results shows the minimum return your account needs to survive your full retirement.

    **Constant inputs.** The investment return, COLA, and step increase you enter are treated as fixed values applied every year. Real markets and salary schedules fluctuate, and a few bad return years early in retirement hurt far more than a steady average suggests. The *What If the Market Has Bad Years?* page simulates this for the return rate; COLA and step increases remain flat.

    **Both options pay the same annual income.** This is not a comparison about how much you receive each year. The question is whether your account has money left over after covering all those payments through retirement. The same COLA rate is applied to both the pension payment and the withdrawal from your own account; in practice they can differ.

    **Equal tax treatment for both options.** The contribution rate is applied to the personal account on the same pre-tax basis as the pension. This is fine if you have room in a 457(b) plan (a tax-advantaged account available to government employees, similar to a 401k), which has its own contribution limit separate from your pension. But if you have no tax-advantaged space available, the personal account is actually disadvantaged in a way that is not factored in here.

    **Only your own contributions are compared.** Most pensions are also funded by your employer. This comparison assumes only your share of the money goes into your own account; the employer's share does not follow you, so it is not counted there.

    **Vesting and leaving early matter.** With fewer than 5 years of service there is no pension, only a refund of your contributions with interest. With 5 or more years but under 30, the pension can't start before age 60; leaving earlier gives a deferred pension from 60 with no COLA. The input panel estimate applies both rules. Survivor and disability benefits are not modeled.

    **Annual, end-of-period timing.** All contributions, deposits, and withdrawals are modeled as single lump sums at the end of each year rather than spread across pay periods. See the *Timing Assumptions* note on the input panel for the exact ordering used. Contributions and withdrawals follow your inputs exactly with no irregular saving or mid-year deviations.

    *Real retirement decisions should involve a licensed financial planner and tax professional who can account for your full situation.*
    """)

    if inputs["plan_status"] == "unvested":
        _first_tip = (
            f"- **In this estimate, fewer than {simulation.PLAN_VESTING_YEARS} years of service "
            f"means a contribution refund instead of a lifetime pension.** The result shows the "
            f"estimated refund under the assumptions entered."
        )
    else:
        _first_tip = (
            f"- **The break-even return is {fmt_rate(res['breakeven_rate'])} per year in this "
            f"scenario.** That is the steady annual return the account would need, under this "
            f"calculator's assumptions, to last through the retirement period shown. It is a "
            f"comparison point, not a prediction of future returns."
        )
    st.header("Understanding This Estimate")
    st.markdown(f"""
This comparison uses the inputs above to show how a pension and a personal account might compare. It does not predict investment results or determine what is right for you. A few points that may help explain the estimate:

{_first_tip}
- **This comparison assumes the same yearly payment from either option.** It does not include survivor or disability benefits, taxes on actual withdrawals, or other personal circumstances described above.
- **For a pension estimate specific to you, check the rules and figures with your plan's retirement office.** The manual amount field lets you enter a monthly or yearly payment before taxes; payment timing and annual increases still follow the built-in rules described in the input panel.

*This calculator is for exploring a scenario. It is not a personal financial recommendation.*
""")

    st.divider()
    st.header("Year-Over-Year Breakdown")

    # Tables always show future dollars so each row's arithmetic adds up, and
    # carry an Age column that matches the chart's age axis.
    table_data = st.session_state["_results_nominal"]["yearly_data"].copy()
    table_data.insert(1, "Age", ages_for(inputs)[1:])
    if res.get("real_dollars"):
        st.caption("These tables show amounts paid in each year, without adjusting for inflation, even when buying power is switched on above. This keeps each row's arithmetic easy to follow.")

    st.markdown("""
Each row is one year. The left table tracks **the pension**, while the right tracks **your own account**. Both tables use amounts paid or held in the year shown. The bold **Total** row adds these amounts without adjusting for inflation. To compare these totals with the summary amounts, switch off **Show buying power at today's prices** above.
""")

    with st.expander("Working Years"):
        st.markdown("""
During your working years, a fixed percentage of your salary is contributed annually. Your salary grows each year from Cost of Living Adjustments (COLA), step increases, and any promotions.
""")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**The Pension**")
            st.markdown(f"""
Each year, {pension_contribution_rate*100:.0f}% of your salary is deducted and paid into the pension. The **Contribution** column shows that deduction. The **Total Contributed** column is a running sum of all contributions to date.

Salary grows each year by your COLA ({cola_pct:.1f}%), plus a step increase ({step_pct:.1f}%) in your first {inputs["step_count"]} years, plus a {promotion_pct:.0f}% bump in any promotion years ({", ".join(str(y) for y in promotion_years) if promotion_years else "none entered"}).{" Year 1 is a special case: it averages your Step 1 and Step 2 salaries, since the Step 1→2 raise happens 6 months in." if inputs["first_step_midyear"] and inputs["step_count"] else ""}
""")
        with col2:
            st.markdown("**Your Own Account**")
            st.markdown(f"""
Instead of paying into the pension, imagine depositing that same amount each year into your own investment account. The column headers show the formula: the **Start Balance** earns **+ Returns** (investment growth at {index_return_pct:.1f}%/year), then the **+ Deposit** (same as the pension contribution) is added, producing the **= Balance** at year-end.

Returns are calculated on the balance at the *start* of the year, before that year's deposit is added.
""")
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                render_breakdown_table(
                    table_data[["Year", "Age", "Salary", "Pension Contribution", "Pension Contribution Total"]],
                    "W",
                    {"Pension Contribution": "Contribution", "Pension Contribution Total": "Total Contributed"},
                ),
                hide_index=True,
            )
        with col2:
            st.dataframe(
                render_breakdown_table(
                    table_data[["Year", "Age", "Start Balance", "Market Returns", "Pension Contribution", "Balance"]],
                    "W",
                    {"Market Returns": "+ Returns", "Pension Contribution": "+ Deposit", "Balance": "= Balance"},
                    balance_col="= Balance",
                ),
                hide_index=True,
            )

    with st.expander("Retirement Years"):
        if inputs["plan_status"] == "unvested":
            _pension_start = "There are no pension payments in this scenario. The contribution refund is shown above."
        elif inputs["deferral_years"]:
            _pension_start = (
                f"Once you leave, contributions stop. The pension does not start until age "
                f"{inputs['retirement_age'] + inputs['deferral_years']}, and then pays the same dollar "
                f"amount every year (no COLA), so neither option pays anything before that."
            )
        else:
            _pension_start = (
                "Once you retire, contributions stop. The pension begins paying you a fixed annual "
                "allowance that grows each year with COLA."
            )
        st.markdown(f"""
{_pension_start} Your account tries to pay the same amount each year and earns returns on its remaining balance. Once it is empty, the **Income Unpaid** column shows payments it could not cover. That is missing income, not debt.
""")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**The Pension**")
            st.markdown(f"""
The pension pays a set annual amount, {f'growing by {res["retiree_cola_pct"]:.1f}% each year (COLA)' if res["retiree_cola_pct"] else 'the same every year (no COLA)'}. **Pension Received** is that year's payment. **Total Received** is the running sum of all payments to date.
""")
        with col2:
            st.markdown("**Your Own Account**")
            st.markdown(f"""
The **Start Balance** earns **+ Returns** ({index_return_pct:.1f}%/year before inflation), then the amount actually paid (**− Withdrawal**) is subtracted, leaving **= Balance**. The account cannot pay more than it holds. **Income Unpaid** is the part of the pension payment it could not match.
""")
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(
                render_breakdown_table(
                    table_data[["Year", "Age", "Pension Redeemed", "Pension Redeemed Total"]],
                    "R",
                    {"Pension Redeemed": "Pension Received", "Pension Redeemed Total": "Total Received"},
                ),
                hide_index=True,
            )
        with col2:
            st.dataframe(
                render_breakdown_table(
                    account_payment_table(table_data)[["Year", "Age", "Start Balance", "Market Returns", "Account Withdrawal", "Income Unpaid", "Balance"]],
                    "R",
                    {"Start Balance": "Start Balance",
                     "Market Returns": "+ Returns",
                     "Account Withdrawal": "− Withdrawal",
                     "Balance": "= Balance"},
                    balance_col="= Balance",
                ),
                hide_index=True,
            )

    st.divider()
    st.header("Case Studies")
    st.caption("Case-study totals below add amounts paid in each year, without adjusting for inflation, regardless of the display switch above. Figures labeled 'today's dollars' show buying power at today's prices. All investment returns are before inflation.")
    if "_before_example" in st.session_state:
        st.button("Restore my previous inputs", key="restore_example_inputs", on_click=restore_previous_inputs)

    st.markdown("""
These examples show accounts that cover all pension payments and accounts that run short. To see the full charts and tables for any of them, click its **Try this scenario** button (or copy the listed settings into the calculator above). Each button also sets the market-swings slider on the second page to 15%, which the "out of 100 possible futures" figures below assume.
""")

    with st.expander("Case Study A: Account Covers All Payments"):
        st.markdown("""
**Settings:** Starting wage \\$120,000 · Step increase 5.5% · Salary COLA 3% · Pension COLA 2% · Promotions at years 10 and 20 (8% each) · Pension contribution rate 10% · Index returns 10% · Work years 30 · Retires at 55 · Retirement years 30 · Plan factor 2% (first-year allowance about \\$238,100, or \\$110,700 in today's dollars)
""")
        if st.button("Try Alice's scenario in the calculator", key="load_alice", icon="▶️"):
            queue_preset("alice")
        st.markdown("""
---

Alice is a civil servant who starts at \\$120,000. Across a 30-year career, her salary climbs through step increases, COLA adjustments, and two promotions. Every year, 10% of it goes into the pension.

**The pension:** By the time Alice retires, she has paid about **\\$770,000** into the pension. In return, she gets an allowance that starts around \\$238,100 a year (about \\$110,700 in today's dollars, since 30 years of raises and inflation come first) and rises 2% annually. Add up 30 years of those payments and she collects roughly **\\$9.7 million**.

**Her own account:** Now suppose she had put those same contributions into an account earning 10% a year instead. By retirement it would hold about **\\$3.2 million**. She then withdraws the same amount the pension would have paid each year. Since 10% growth outpaces what she takes out, the balance keeps climbing through retirement and finishes close to **\\$10 million**.

**Result under these assumptions:** The account covers every payment and finishes with money left. Both options pay Alice the exact same income every year she is retired. The pension never hands her an extra dollar. The whole difference is what is left at the end. Her own account still holds close to \\$10 million that she owns and can pass to her family, while the pension leaves nothing once she dies. At a steady return of 9.2% or less, the account cannot cover all payments. And it assumes a steady 10% every single year. With simulated ups and downs, Alice's fund runs out in about 38 out of 100 possible futures (see the *What If the Market Has Bad Years?* page).

This is also the scenario people misread most often. They see "\\$9.7 million in pension income" and assume the pension came out ahead, but that number is just the running total of Alice's annual payments; keep in mind that her own account paid out that same amount! The \\$10 million is *extra* that she gets to keep (donate, pass on, etc.), on top of the \\$9.7 million that she already withdrew and spent during her life.
""")

    with st.expander("Case Study B: Account Runs Short"):
        st.markdown("""
**Settings:** Starting wage \\$65,000 · Step increase 5.5% · Salary COLA 3% · Pension COLA 2% · No promotions · Pension contribution rate 10% · Index returns 5% · Work years 20 · Retires at 60 · Retirement years 35 · Plan factor 1.5% (first-year allowance about \\$41,100, or \\$24,500 in today's dollars)
""")
        if st.button("Try Bob's scenario in the calculator", key="load_bob", icon="▶️"):
            queue_preset("bob")
        st.markdown("""
---

Bob is a civil servant who starts at \\$65,000 and works a steady 20 years with no promotions. He retires at 60 and then spends 35 years in retirement before he dies. Over that lifetime the market returns a modest 5% a year.

**The pension:** During his 20 working years, Bob pays about **\\$212,000** into the pension. In retirement he collects around \\$41,100 the first year, rising 2% annually. Stretched over 35 years, that comes to roughly **\\$2.1 million**, nearly 10 times what he put in.

**His own account:** Those same contributions, growing at 5% a year, would leave Bob with about **\\$332,000** at retirement. Once he starts pulling out \\$41,100 a year (rising 2% annually), the growth cannot keep up with the withdrawals. The account runs dry in **year 10**, leaving nothing for his final 25 years.

**Result under these assumptions:** The account cannot cover all modeled payments. At 5% returns, a \\$332,000 balance just cannot fund 35 years of withdrawals. What carries him through is the pension's promise to keep paying for as long as he lives. Without it, he runs out of money around age 70.

Lower returns, a longer retirement, or fewer years of contributions can make it harder for the account to cover the modeled payments.
""")

    with st.expander("Case Study C: Account Covers All Payments"):
        st.markdown("""
**Settings:** Starting wage \\$80,000 · Step increase 5.5% · Salary COLA 3% · Pension COLA 2% · Promotion at year 15 (8%) · Pension contribution rate 10% · Index returns 9% · Work years 35 · Retires at 60 · Retirement years 25 · Plan factor 2% (first-year allowance about \\$198,800, or \\$81,700 in today's dollars)
""")
        if st.button("Try Carol's scenario in the calculator", key="load_carol", icon="▶️"):
            queue_preset("carol")
        st.markdown("""
---

Carol is a civil servant who starts at \\$80,000 and works a long 35-year career, earning one promotion along the way. Every year, 10% of her salary goes into the pension. She retires at 60 and spends 25 years in retirement, with the market returning a steady 9% a year.

**The pension:** Over 35 working years, Carol pays about **\\$628,000** into the pension. In return she collects an allowance that starts at \\$198,800 and rises 2% annually. Across 25 years of retirement those payments add up to roughly **\\$6.4 million**.

**Her own account:** Those same contributions, growing at 9% a year, would hold about **\\$2.9 million** by the time she retires. She then withdraws the same amount the pension would have paid each year. Because 9% growth stays ahead of what she takes out, the balance keeps rising through retirement and finishes above **\\$5.2 million**.

**Result under these assumptions:** The account covers every payment and finishes with money left. Both options pay Carol the identical \\$6.4 million of income across her retirement; the difference is that her own account still holds over \\$5.2 million she owns and can pass on, while the pension leaves nothing once she dies. A long career and a return comfortably above the withdrawal pace are what tip it her way. The catch is the word *steady*: with simulated ups and downs, her fund runs out in about 34 out of 100 possible futures.
""")

    with st.expander("Case Study D: Account Runs Short"):
        st.markdown("""
**Settings:** Starting wage \\$95,000 · Step increase 5.5% · Salary COLA 3% · Pension COLA 2% · No promotions · Pension contribution rate 10% · Index returns 4% · Work years 15 · Retires at 63 · Retirement years 25 · Plan factor 2% (first-year allowance about \\$51,900, or \\$34,900 in today's dollars)
""")
        if st.button("Try Dave's scenario in the calculator", key="load_dave", icon="▶️"):
            queue_preset("dave")
        st.markdown("""
---

Dave is a civil servant who starts at \\$95,000 but works only 15 years before retiring at 63. He then spends 25 years in retirement, and over that stretch the market returns a modest 4% a year.

**The pension:** During his 15 working years, Dave pays about **\\$213,000** into the pension. In retirement he collects \\$51,900 the first year, rising 2% annually. Stretched over 25 years, that comes to roughly **\\$1.7 million**, nearly 8 times what he put in.

**His own account:** Those same contributions, growing at 4% a year, would leave Dave with only about **\\$276,000** at retirement. Once he starts withdrawing \\$51,900 a year (rising 2% annually), a balance that small cannot keep up. The account runs dry in **year 6** of retirement, leaving nothing for his final 19 years.

**Result under these assumptions:** The contributions from this 15-year career, earning 4% a year, do not fund all 25 years of modeled payments. What carries Dave through is the pension's promise to keep paying for as long as he lives. This is Bob's problem in a sharper form: fewer working years and lower returns.
""")

    with st.expander("Case Study E: Account Runs Short (Hired Late)"):
        st.markdown("""
**Settings:** Starting wage \\$90,000 · Step increase 5.5% · Salary COLA 3% · Pension COLA 2% · No promotions · Pension contribution rate 10% · Index returns 7% · Hired at 50 · Retires at 63 (13 years of work) · Retirement years 25 · Plan factor 2% (first-year allowance about \\$40,100, or \\$28,400 in today's dollars)
""")
        if st.button("Try Grace's scenario in the calculator", key="load_grace", icon="▶️"):
            queue_preset("grace")
        st.markdown("""
---

Grace changes careers and is hired at 50, starting at \\$90,000 with no promotions. She works 13 years, retires at 63, and then spends 25 years in retirement, with the market returning a steady 7% a year.

**The pension:** Over 13 working years, Grace pays about **\\$169,000** into the pension. Because she waits until 63, she earns the plan's 2% per year of service instead of the 1.5% she would get by retiring at 60. Her allowance starts at about \\$40,100 a year and rises 2% annually. Over 25 years that adds up to roughly **\\$1.3 million**, nearly 8 times what she put in.

**Her own account:** Those same contributions, growing at 7% a year, would hold only about **\\$251,000** when she retires. Once she starts withdrawing \\$40,100 a year (rising 2% annually), the account runs dry in **year 8**, leaving nothing for her final 17 years.

**Result under these assumptions:** The account cannot cover all payments after this 13-year career. The modeled pension continues paying. Her own account would need a steady 12.5% a year just to break even, and with simulated ups and downs it runs out in about 97 out of 100 possible futures. The result depends on the contribution period, return, retirement duration, and pension formula entered.
""")

    with st.expander("Case Study F: Account Covers All Payments"):
        st.markdown("""
**Settings:** Starting wage \\$150,000 · Step increase 5.5% · Salary COLA 3% · Pension COLA 2% · Promotions at years 10 and 18 (10% each) · Pension contribution rate 10% · Index returns 10% · Work years 25 · Retires at 60 · Retirement years 25 · Plan factor 1.5% (first-year allowance about \\$166,500, or \\$87,600 in today's dollars)
""")
        if st.button("Try Frank's scenario in the calculator", key="load_frank", icon="▶️"):
            queue_preset("frank")
        st.markdown("""
---

Frank is a civil servant who starts at \\$150,000 and earns two sizable promotions across a 25-year career. Every year, 10% of his salary goes into the pension. He then spends 25 years in retirement, with the market returning a strong 10% a year. Retiring at 60 without 30 years of service, he earns the plan's lower 1.5% per year of service.

**The pension:** Over 25 working years, Frank pays about **\\$742,000** into the pension. In return he collects an allowance that starts at \\$166,500 and rises 2% annually, adding up to roughly **\\$5.3 million** across retirement.

**His own account:** Those same contributions, growing at 10% a year, would hold about **\\$2.4 million** by retirement. He then withdraws the same amount the pension would have paid. With 10% growth running well ahead of his withdrawals, the balance climbs throughout retirement and finishes above **\\$6.5 million**.

**Result under these assumptions:** The account covers every payment and finishes with money left. The \\$5.3 million of pension income is matched dollar for dollar by his own account, which then leaves over \\$6.5 million on top for Frank to keep or pass on. This result depends on the contributions, assumed returns, and pension formula used here. Even so, with simulated ups and downs instead of a steady 10%, his fund runs out in about 31 out of 100 possible futures.
""")

    render_feedback_form("comparison")
