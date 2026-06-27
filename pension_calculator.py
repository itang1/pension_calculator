import math
import streamlit as st
import pandas as pd
from plotly import graph_objects as go

st.set_page_config(layout="wide")


def render_breakdown_table(df, phase_prefix, rename_map, balance_col=None):
    """Render one side of the year-over-year breakdown.

    Filters ``df`` to the rows for the given phase (``"W"`` or ``"R"``),
    renames columns, appends a summary ("Total") row, formats every dollar
    column, and—if ``balance_col`` is given—colors negative balances red so a
    depleted personal fund is easy to spot.
    """
    table = df[df["Year"].str.startswith(phase_prefix)].copy()
    table = table.rename(columns=rename_map)

    money_cols = [c for c in table.columns if c != "Year"]

    # Build a summary row. Running-total and balance columns take their final
    # value; flow columns (contributions, deposits, withdrawals, returns) are
    # summed. Per-year salary is a snapshot, so it is left blank in the total.
    total_row = {"Year": "Total"}
    for col in money_cols:
        renamed_running = {rename_map.get(k, k) for k in (
            "Pension Contribution Total", "Pension Redeemed Total")}
        renamed_balance = {rename_map.get(k, k) for k in ("Balance",)}
        if col in renamed_running or col in renamed_balance:
            total_row[col] = table[col].iloc[-1] if len(table) else 0.0
        elif col == rename_map.get("Salary", "Salary") or col == rename_map.get("Start Balance", "Start Balance"):
            total_row[col] = float("nan")
        else:
            total_row[col] = table[col].sum()
    table = pd.concat([table, pd.DataFrame([total_row])], ignore_index=True)

    def _highlight_negative(val):
        if isinstance(val, (int, float)) and pd.notna(val) and val < 0:
            return "color: #d62728; font-weight: 600;"
        return ""

    def _bold_total(row):
        return ["font-weight: 700;" if row["Year"] == "Total" else "" for _ in row]

    styler = table.style.format("${:,.0f}", subset=money_cols, na_rep="—")
    styler = styler.apply(_bold_total, axis=1)
    if balance_col is not None:
        styler = styler.map(_highlight_negative, subset=[balance_col])
    return styler


st.title("Is Your Pension Worth It?")

st.markdown("""
Many public employees (such as teachers, law enforcement officers, and civil servants) are mandatorily required to contribute part of each paycheck to a pension plan (e.g. a flat 10%). In return, the pension pays a guaranteed annual benefit in retirement for life, regardless of market performance.

In this website, we ask the question: **Instead of participating in the pension program, if an employee had the alternative option to invest that same money into their own personal retirement account, which of the two options would produce better outcomes for them?**
""")

st.markdown("""
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<em>&larr; On the left sidebar, enter your own assumptions about salary, contribution rate, investment return, and retirement timeline to see how the two options compare.</em>
</div>

""", unsafe_allow_html=True)

st.space()

with st.expander("Explanation of the Two Options"):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
<div style="background-color:#FEF3C7; border-left:5px solid #D97706; padding:1rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Option A: Traditional Pension</strong><br><br>
Each year, a fixed percentage of your paycheck (e.g. 10%) is automatically deducted and funneled directly into your organization's pension system. The funds are then managed by professional fund managers who ensure its long-term stability and growth. In return, once you retire, the pension program will pay you a guaranteed annual payment for the rest of your life, regardless of broad market performance. (The specific amount will depend on your salary, years of service, and the pension formula used by your organization.)
</div>
""", unsafe_allow_html=True)
    with col_b:
        st.markdown("""
<div style="background-color:#CCFBF1; border-left:5px solid #0D9488; padding:1rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Option B: Personal Retirement Account</strong><br><br>
Instead of contributing to the pension, imagine that you deposit that same amount (e.g. 10%) each year into your own personal investment account. You have total control over how to invest the funds, and the balance will grow with market returns depending on your investment choices. Imagine that in retirement, you choose to withdraw the same annual amount that the pension would have paid. Additionally, any remaining balance in your account at the end of your life is yours to keep or donate as well.
</div>
""", unsafe_allow_html=True)

with st.expander("Limitations & Assumptions of the Tool"):
    st.markdown("""
This calculator is an educational tool, not a comprehensive financial model. The inputs you provide are applied with several simplifying assumptions:

**Constant input rates.** The investment return, COLA, and step increase you enter are treated as fixed values applied every year. Real markets and salary schedules fluctuate, and a few bad return years early in retirement hurt far more than a steady average suggests.

**Equal tax treatment for both options.** The contribution rate is applied to the personal account on the same pre-tax basis as the pension. This is fine if you have room in a 457(b) plan, which has its own contribution limit, separate from your pension). But if you have no tax-advantaged space available, the personal account is actually disadvantaged in a way that is not factored in here.

**Annual, end-of-period timing.** All contributions, deposits, and withdrawals are modeled as single lump sums at the end of each year rather than spread across pay periods, which is a simplification. See the "Timing Assumptions" note for the exact ordering used.

**Steady contribution and withdrawal amounts.** Contributions follow your salary inputs, and withdrawals match the pension allowance exactly. The tool does not model any deviations such as irregular saving, retiring in the middle of the year, or altering your withdrawal rate from year to year.

*Real retirement decisions should involve a licensed financial planner and tax professional who can account for your full situation.*
""")


# Input form sidebar
with st.sidebar:
    st.header("Input Assumptions")

    with st.expander("Timing Assumptions"):
        st.markdown("""
This calculator operates in annual periods. Within each year:
- **Contributions & deposits**: Made at the end of the year.
- **Withdrawals**: Made at the end of the year.
- **Market returns**: Earned on the balance at the *start* of the year, before that year's deposit or withdrawal.
- **COLA**: Applied to salary at the end of each working year, taking effect the following year. In retirement, applied to the pension allowance at the end of each year, taking effect the following year.
- **Step increases**: The Step 1 → Step 2 raise occurs 6 months after hire. Since the calculator uses annual periods, Year 1 contributions are averaged over 6 months at Step 1 and 6 months at Step 2. The Steps 2 → 3, 3 → 4, and 4 → 5 raises each take effect at the start of Years 3, 4, and 5 respectively.
- **Promotions**: Applied at the end of the year you specify, taking effect the following year.
""")

    st.subheader("Career")
    starting_wage = st.number_input(
        "Starting Annual Wage ($)",
        value=50000,
        min_value=0,
        step=2500,
        help="Your initial salary for the first year you were hired."
    )
    work_years = st.number_input(
        "Years to Work",
        value=30,
        min_value=1,
        step=1,
        help="How many years you plan to work before retirement."
    )
    cola_increase = st.number_input(
        "Cost of Living Adjustment (%)",
        value=3.0,
        min_value=2.5,
        max_value=5.5,
        step=0.1,
        help="Annual salary adjustment announced each October, typically between 2–3.5%."
    ) / 100 + 1
    step_increase = st.number_input(
        "Step Increase (%)",
        value=5.5,
        min_value=0.,
        step=0.1,
        help="Annual raise from step progression (e.g., moving up a salary scale)."
    ) / 100 + 1
    promotion_years_input = st.text_input(
        "Promotion Years",
        value="10, 20",
        help="Year numbers in which you expect to be promoted (e.g., 10, 20). Should fall within your working years."
    )
    promotion_increase = st.number_input(
        "Promotion Increase (%)",
        value=8.0,
        step=1.,
        help="Expected salary bump when you receive a promotion."
    ) / 100 + 1

    st.subheader("Pension")
    pension_contribution_rate = st.number_input(
        "Pension Contribution Rate (%)",
        value=10.0,
        step=1.,
        help="Percentage of your salary automatically deducted and contributed to the pension system each year."
    ) / 100
    starting_allowance = st.number_input(
        "Starting Annual Pension Allowance ($)",
        value=12 * 5871.52,
        step=2500.,
        help="Estimate your annual pension payout in your first year of retirement, before COLA adjustments. You can calculate yours using the designated pension calculator website."
    )

    st.subheader("Retirement")
    retirement_years = st.number_input(
        "Years Alive After Retirement",
        value=30,
        min_value=1,
        max_value=60,
        step=1,
        help="How many years you expect to live after retiring."
    )
    index_returns_rate = st.number_input(
        "Index Returns Rate (%)",
        value=7.0,
        step=0.1,
        help="Expected annual return rate of your hypothetical personal retirement investments."
    ) / 100 + 1

# Results
st.divider()
st.header("Simulation Results: Pension vs. Personal Fund")

# Parse promotion years
try:
    promotion_years = [int(y.strip()) for y in promotion_years_input.split(",") if y.strip().isdigit()]
except:
    promotion_years = []

# Initialize variables
pension_contribution_total = 0
pension_redeemed_total = 0
personal_balance = 0
salary = starting_wage
pension_redeemed = starting_allowance

# Tracking for visualization
years = ["W0"]
pension_fund_values = [0]
personal_fund_values = [0]
# Per-year hover data: [contribution, disbursement, deposit, withdrawal, market_returns]
hover_data = [[0, 0, 0, 0, 0]]
yearly_data = pd.DataFrame({'Year': pd.Series(dtype='str'),
                            'Salary': pd.Series(dtype='float'),
                            'Start Balance': pd.Series(dtype='float'),
                            'Pension Contribution': pd.Series(dtype='float'),
                            'Pension Contribution Total': pd.Series(dtype='float'),
                            'Pension Redeemed': pd.Series(dtype='float'),
                            'Pension Redeemed Total': pd.Series(dtype='float'),
                            'Market Returns': pd.Series(dtype='float'),
                            'Balance': pd.Series(dtype='float')})

# Work phase - Loop through the work years
for work_year in range(1, int(work_years) + 1):
    # Year 1: Step 1→2 occurs at 6 months, so average Step 1 and Step 2 salaries
    if work_year == 1:
        effective_salary = salary * (1 + step_increase) / 2
    else:
        effective_salary = salary

    # Compute pension contribution
    pension_contribution_this_year = effective_salary * pension_contribution_rate
    pension_contribution_total += pension_contribution_this_year

    # Compute personal balance
    start_balance = personal_balance
    market_returns = personal_balance * (index_returns_rate-1)
    personal_balance = personal_balance + market_returns + pension_contribution_this_year

    years.append(f"W{work_year}")
    pension_fund_values.append(0)
    personal_fund_values.append(personal_balance)
    hover_data.append([pension_contribution_this_year, 0, pension_contribution_this_year, 0, market_returns])

    # Store data for the table (numeric; formatted at display time)
    new_row = {
        "Year": f"W{work_year}",
        "Salary": effective_salary,
        "Start Balance": start_balance,
        "Pension Contribution": pension_contribution_this_year,
        "Pension Contribution Total": pension_contribution_total,
        "Pension Redeemed": 0.0,
        "Pension Redeemed Total": 0.0,
        "Market Returns": market_returns,
        "Balance": personal_balance
    }
    yearly_data = pd.concat([yearly_data, pd.DataFrame([new_row])], ignore_index=True)

    # Update salary for next year
    salary *= cola_increase
    if 1 <= work_year < 5:
        salary *= step_increase
    if work_year in promotion_years:
        salary *= promotion_increase

# Retirement phase - Loop through the retirement years
for ret_year in range(1, retirement_years + 1):
    # Pension redemptions
    pension_redeemed_total += pension_redeemed

    # Personal fund
    start_balance = personal_balance
    market_returns = personal_balance * (index_returns_rate-1)
    personal_balance = personal_balance - pension_redeemed + market_returns

    years.append(f"R{ret_year}")
    pension_fund_values.append(pension_redeemed_total)
    personal_fund_values.append(personal_balance)
    hover_data.append([0, pension_redeemed, 0, pension_redeemed, market_returns])

    # Store data for the table (numeric; formatted at display time)
    new_row = {"Year": f"R{ret_year}",
        "Salary": float('nan'),
        "Start Balance": start_balance,
        "Pension Contribution": 0.0,
        "Pension Contribution Total": 0.0,
        "Pension Redeemed": pension_redeemed,
        "Pension Redeemed Total": pension_redeemed_total,
        "Market Returns": market_returns,
        "Balance": personal_balance
    }
    yearly_data = pd.concat([yearly_data, pd.DataFrame([new_row])], ignore_index=True)

    # Update allowance for next year
    pension_redeemed *= cola_increase

# Plot
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=years,
    y=pension_fund_values,
    mode='lines+markers',
    name='Pension: total income received so far',
    line=dict(color='#D97706'),
    customdata=hover_data,
    hovertemplate=(
        '<b>Year %{x}</b><br>'
        'Contribution this year: $%{customdata[0]:,.0f}<br>'
        'Pension payment this year: $%{customdata[1]:,.0f}<br>'
        'Cumulative total received: $%{y:,.0f}'
        '<extra></extra>'
    )
))

fig.add_trace(go.Scatter(
    x=years,
    y=personal_fund_values,
    mode='lines+markers',
    name='Personal fund: money left in the account',
    line=dict(color='#0D9488'),
    customdata=hover_data,
    hovertemplate=(
        '<b>Year %{x}</b><br>'
        'Deposit this year: $%{customdata[2]:,.0f}<br>'
        'Withdrawal this year: $%{customdata[3]:,.0f}<br>'
        'Market returns this year: $%{customdata[4]:,.0f}<br>'
        'Fund balance: $%{y:,.0f}'
        '<extra></extra>'
    )
))

# Adaptive x-axis
total_years = len(years)
x_tick_step = max(5, int(math.ceil(total_years / 10 / 5) * 5))

# Adaptive y-axis
all_values = [v for v in pension_fund_values + personal_fund_values if v is not None]
data_min = min(all_values, default=0)
data_max = max(all_values, default=1)
data_range = max(data_max - data_min, 1)
raw_interval = data_range / 8
magnitude = 10 ** math.floor(math.log10(raw_interval))
normalized = raw_interval / magnitude
if normalized <= 1:
    nice = 1
elif normalized <= 2:
    nice = 2
elif normalized <= 2.5:
    nice = 2.5
elif normalized <= 5:
    nice = 5
else:
    nice = 10
y_tick_interval = nice * magnitude

fig.update_layout(
    title='Pension vs. Personal Retirement Fund Over Time',
    xaxis_title='Year (W = Working, R = Retirement)',
    yaxis_title='Dollar Amount ($)',
    xaxis=dict(
        tickangle=45,
        tickmode='array',
        tickvals=[years[i] for i in range(0, len(years), x_tick_step)],
        tickfont=dict(size=10),
        showgrid=True,
        gridcolor='lightgray',
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor='lightgray',
        dtick=y_tick_interval,
        tickformat=',',
        separatethousands=True,
    ),
    plot_bgcolor='white',
    legend=dict(x=0.01, y=0.99),
    margin=dict(l=40, r=20, t=60, b=100)
)

fig.add_vline(x=work_years, line_width=3, line_dash="dash", line_color="red", annotation_text="Retirement begins here",
          annotation_position="top right")

# Emphasize the zero baseline
fig.add_hline(y=0, line_width=2, line_color="#666666",
          annotation_text="$0 — personal fund depleted",
          annotation_position="bottom right")

st.markdown("""
**How to read this chart**

Here, we imagine that both options pay you the **same income every year in retirement**. This brings the whole comparison down to the question: **does your personal fund run out before you die?**

- **Teal line = how much remains in your personal fund after withdrawing your annual allotment.** If it stays above zero, the personal fund wins. If it reaches zero, the pension wins.
- **Amber line = running tally of how much pension income received so far.** Shown only for scale. A high amber line does **not** mean that the pension is winning. Both options pay this exact income, so don't compare the two lines against each other.
- **Red dashed line = the year retirement begins.**
- **Light gray line = the $0 mark.** If the teal line touches this, the personal fund has run out of money.
""")

st.plotly_chart(fig, use_container_width=True)

if personal_balance > 0:
    st.success(f"""
**Based on your inputs, the personal fund is viable.**

After {int(retirement_years)} years of retirement, your personal fund would still have **\\${personal_balance:,.0f}** remaining for you to keep (donate, pass on, etc.), on top of having already paid out the same income as the pension every single year. The pension would leave nothing (besides potential survivor benefits, if applicable).
""")
else:
    st.info(f"""
**Based on your inputs, the pension is the better option.**

Before your {int(retirement_years)}-year retirement was over, your personal fund would have fully depleted, while the pension would have kept paying. Your investment returns can't sustain that many years of withdrawals, so you should choose the pension for its lifetime guarantee.
""")

mc1, mc2 = st.columns(2)
with mc1:
    st.metric(
        label="Pension Contributed",
        value=f"${pension_contribution_total:,.0f}",
        help="The total amount automatically deducted from your paychecks and paid into the pension system over your working years."
    )
with mc2:
    st.metric(
        label="Pension Received",
        value=f"${pension_redeemed_total:,.0f}",
        delta=f"${pension_redeemed_total - pension_contribution_total:,.0f} net",
        help="The total pension income paid out over all retirement years, including annual COLA increases. The delta shows how much more you received than you put in."
    )

mc3, mc4 = st.columns(2)
with mc3:
    st.metric(
        label="Fund at Retirement",
        value=f"${personal_fund_values[work_years]:,.0f}",
        help="The balance of your hypothetical personal investment account on the day you retire, after years of contributions and market growth."
    )
with mc4:
    if personal_balance > 0:
        st.metric(
            label="Fund at Death",
            value=f"${personal_balance:,.0f}",
            delta="Did not run out ✓",
            help="The personal fund still has money left after paying out the same income as the pension for every retirement year. This is money you'd still own at death."
        )
    else:
        st.metric(
            label="Fund at Death",
            value=f"${personal_balance:,.0f}",
            delta="Ran out before death ✗",
            delta_color="inverse",
            help="The personal fund was depleted before your retirement years were up. The pension would have continued paying regardless."
        )

st.markdown("""
**What you leave behind at your death:**
- With the **personal fund**, whatever the teal line shows at the end of retirement is money you still own (to donate, pass on, etc.)
- With the **pension**, payments stop when you die (unless you elected an option that includes a *survivor benefit*, which is a reduced annual payment to a spouse or dependent after your death). This calculator does not model survivor benefits.
""")

# Display the table
st.divider()
st.subheader("Year-Over-Year Breakdown")

st.markdown("""
Each row is one year. The left table tracks the **pension side**, while the right tracks the **personal fund side**. They use the same dollar amounts each year so the comparison is apples-to-apples. The bold **Total** row at the bottom of each table ties back to the summary metrics above.
""")

with st.expander("Working Years"):
    st.markdown("""
During your working years, a fixed percentage of your salary is contributed annually. Your salary grows each year from Cost of Living Adjustments (COLA), step increases, and any promotions.
""")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Pension Side**")
        st.markdown(f"""
Each year, {pension_contribution_rate*100:.0f}% of your salary is deducted and paid into the pension. The **Contribution** column shows that deduction. The **Total Contributed** column is a running sum of all contributions to date.

Salary grows each year by your COLA ({(cola_increase-1)*100:.1f}%), plus a step increase ({(step_increase-1)*100:.1f}%) in your first 4 years, plus a {(promotion_increase-1)*100:.0f}% bump in any promotion years ({str(promotion_years).strip("[]") if promotion_years else "none entered"}). Year 1 is a special case: it averages your Step 1 and Step 2 salaries, since the Step 1→2 raise happens 6 months in.
""")
    with col2:
        st.markdown("**Personal Fund Side**")
        st.markdown(f"""
Instead of paying into the pension, imagine depositing that same amount each year into your own investment account. The column headers show the formula: the **Start Balance** earns **+ Returns** (investment growth at {(index_returns_rate-1)*100:.1f}%/year), then the **+ Deposit** (same as the pension contribution) is added, producing the **= Balance** at year-end.

Returns are calculated on the balance at the *start* of the year, before that year's deposit is added.
""")
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(
            render_breakdown_table(
                yearly_data[["Year", "Salary", "Pension Contribution", "Pension Contribution Total"]],
                "W",
                {"Pension Contribution": "Contribution",
                 "Pension Contribution Total": "Total Contributed"},
            ),
            hide_index=True,
        )
    with col2:
        st.dataframe(
            render_breakdown_table(
                yearly_data[["Year", "Start Balance", "Market Returns", "Pension Contribution", "Balance"]],
                "W",
                {"Market Returns": "+ Returns",
                 "Pension Contribution": "+ Deposit",
                 "Balance": "= Balance"},
                balance_col="= Balance",
            ),
            hide_index=True,
        )

with st.expander("Retirement Years"):
    st.markdown("""
Once you retire, contributions stop. The pension begins paying you a fixed annual allowance that grows each year with COLA. The personal fund is drawn down by that same amount each year, but continues earning investment returns on whatever balance remains. If the **= Balance** ever turns red (negative), the personal fund has run out — the year it first goes red is the year the pension's lifetime guarantee starts to matter.
""")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Pension Side**")
        st.markdown(f"""
The pension pays a set annual amount, growing by {(cola_increase-1)*100:.1f}% each year (COLA). **Pension Received** is that year's payment. **Total Received** is the running sum of all payments to date.
""")
    with col2:
        st.markdown("**Personal Fund Side**")
        st.markdown(f"""
Each year, you withdraw the same dollar amount as the pension would have paid. The column headers show the formula: the **Start Balance** earns **+ Returns** ({(index_returns_rate-1)*100:.1f}%/year), then the **− Withdrawal** is subtracted, leaving **= Balance**. If returns exceed the withdrawal, the balance grows. If not, it shrinks.
""")
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(
            render_breakdown_table(
                yearly_data[["Year", "Pension Redeemed", "Pension Redeemed Total"]],
                "R",
                {"Pension Redeemed": "Pension Received",
                 "Pension Redeemed Total": "Total Received"},
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


# Case Studies
st.divider()
st.header("Case Studies")

st.markdown("""
The two examples below show one scenario where each option wins. To see the full charts and tables for either, enter the listed settings into the calculator above.
""")

with st.expander("Case Study A: Personal Fund Wins"):
    st.markdown("""
**Settings:** Starting wage \\$120,000 · Step increase 5.5% · COLA 3% · Promotions at years 10 and 20 (10% each) · Pension contribution rate 10% · Index returns 7% · Work years 30 · Retirement years 30 · First-year pension allowance \\$70,458

---

Alice is a public school administrator who starts at \\$120,000. Across a 30-year career, her salary climbs through step increases, COLA adjustments, and two promotions. Every year, 10% of it goes into the pension.

**The pension:** By the time Alice retires, she has paid about **\\$785,000** into the pension. In return, she gets an allowance that starts around \\$70,458 a year and rises 3% annually. Add up 30 years of those payments and she collects roughly **\\$3.35 million**.

**The personal fund:** Now suppose she had put those same contributions into an account earning 7% a year instead. By retirement it would hold about **\\$2.02 million**. She then withdraws the same amount the pension would have paid each year. Since 7% growth outpaces what she takes out, the balance keeps climbing through retirement and finishes above **\\$6.28 million**.

**Verdict:** The personal fund wins, and it is worth being clear about why. Both options pay Alice the exact same income every year she is retired. The pension never hands her an extra dollar. The whole difference is what is left at the end. The personal fund still holds \\$6.28 million that she owns and can pass to her family, while the pension leaves nothing once she dies.

This is also the scenario people misread most often. They see "\\$3.35 million in pension income" and assume the pension came out ahead, but that number is just the running total of Alice's annual payments; keep in mind that the personal fund paid out that same amount! The \\$6.28 million is *extra* that she gets to keep (donate, pass on, etc.), on top of the \\$3.35 million that she already withdrew and spent during her life.
""")

with st.expander("Case Study B: Pension Wins"):
    st.markdown("""
**Settings:** Starting wage \\$65,000 · Step increase 5.5% · COLA 3% · No promotions · Pension contribution rate 10% · Index returns 5% · Work years 20 · Retirement years 40 · First-year pension allowance \\$27,000

---

Bob is a civil servant who starts at \\$65,000 and works a steady 20 years with no promotions. He retires fairly early and then spends 40 years in retirement. Over that lifetime the market returns a modest 5% a year.

**The pension:** During his 20 working years, Bob pays about **\\$175,000** into the pension. In retirement he collects around \\$27,000 the first year, rising 3% annually. Stretched over 40 years, that comes to roughly **\\$2 million**, more than 11 times what he put in.

**The personal fund:** Those same contributions, growing at 5% a year, would leave Bob with about **\\$265,000** at retirement. Once he starts pulling out \\$27,000 a year (rising 3% annually), the growth cannot keep up with the withdrawals. The account runs dry in **about 13 years**, leaving nothing for his final 27 years.

**Verdict:** The pension wins because Bob outlives his savings. At 5% returns, a \\$265,000 balance just cannot fund 40 years of withdrawals. What carries him through is the pension's promise to keep paying for as long as he lives. Without it, he runs out of money in his early 70s.

The pension option tends to come out ahead when returns are low, retirement is long, or the personal fund didn't have enough working years to grow.
""")
