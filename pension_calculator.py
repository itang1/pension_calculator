import math
import streamlit as st
import pandas as pd
from plotly import graph_objects as go


st.title("Is Your Pension Worth It?")

st.markdown("""
Many public employees (such as teachers, law enforcement officers, civil servants) are required to contribute a portion of every paycheck into a pension plan, with no say in the matter. But is the pension actually worth it? **What if you had instead kept that money and invested it yourself?**
""")

st.markdown("This calculator compares two options side by side:")

col_a, col_b = st.columns(2)
with col_a:
    st.info("""
**Option A: Traditional Pension**

Each year, a fixed percentage of your paycheck is automatically deducted and paid into the pension system. You don't control this money or decide how it's invested. In exchange, when you retire, the pension pays you a guaranteed fixed amount every year for the rest of your life, no matter how long you live or how the stock market performs.
""")
with col_b:
    st.info("""
**Option B: Personal Retirement Account**

What if, instead of contributing to the pension, you deposited that same amount each year into your own investment account? Your money would grow over time through market returns, and you'd own it outright. After retiring, you withdraw the same annual amount as your pension would have paid, and whatever is left over stays in your account and keeps growing.
""")

st.markdown("""
By running both scenarios with the same inputs (such as salary, contribution rate, investment return, and retirement timeline), you can see which option comes out ahead, and by how much.
""")

st.markdown("""
---
**What's on this page:**

1. **Background:** The pension debate, and what this calculator does and doesn't model**
2. **Input assumptions:** Enter your salary, career details, and retirement estimates
3. **Simulation results:** A side-by-side chart and numeric summary comparing both options
4. **Year over year breakdown:** Detailed tables showing how every number was calculated, year by year
5. **Case studies:** Two worked examples illustrating when each option wins
""")


st.divider()
st.header("Background")


with st.expander("The Pension Debate"):
    st.markdown("""
In order to answer whether the pension is actually worth it, it helps to understand the broader discourse around public pensions.

### The Case Against Pensions

Pension systems were designed for a different era, one where people worked a single job for 30 years, life expectancy was shorter, and personal investing was difficult and expensive. Today, those conditions largely no longer hold.

Critics argue that pensions are financially unsustainable. Many public pension funds are underfunded, such that they owe more in future benefits than they currently hold in assets. When that gap widens, taxpayers bear the cost. Critics also point to structural flaws: pensions disproportionately reward employees who stay for decades, while those who leave before vesting (which sometimes is set to 5 or 10 years) walk away with nothing or very little. In today's climate, where job-hopping every few years is common practice, that's a serious penalty for mobility.

There's also the matter of control. Pension contributions are gone the moment they leave your paycheck. You can't invest them, access them early in an emergency, or pass them to your family if you die before retirement. A personal investment account, by contrast, is your money: it grows on your terms, you can leave it to heirs, and you're not dependent on a government agency to remain solvent for the next 30 years.

### The Case For Pensions

On the other side, defenders of pensions make a compelling argument: guaranteed income for life is genuinely hard to replicate on your own. A pension pays no matter how long you live, regardless of whether the market crashes the year you retire. A personal investment account has no such guarantee. If your investments perform poorly or if you live longer than expected, you can run out of money.

Pensions also provide a kind of collective insurance. When a large pool of workers all contribute together, those who live longest are effectively subsidized by those who don't. An individual investor can't access this "mortality pooling" in a personal account.

Defenders also note that many public sector jobs pay less than their private sector equivalents. The pension is often part of the total compensation package that makes those jobs attractive.

### Is it Worth It?

Both sides have a point, and the research reflects that. Whether a pension is "worth it" for a given individual depends on a web of factors: how long you work and whether you vest fully, how the market performs over your career, how long you live in retirement, whether you have heirs you want to provide for, and how much you value certainty versus upside potential.

This calculator doesn't resolve that debate, but it is a tool to aid in making the comparison transparent. Plug in your own numbers to see for for yourself.
""")

with st.expander("Limitations & Assumptions"):
    st.markdown("""
This calculator is an educational tool, not a comprehensive financial model. Several important factors are simplified or omitted:

**Tax treatment.** This calculator assumes the personal savings option has the same pre-tax advantages as the pension (i.e. contributions reduce your taxable income now, and you pay taxes later). In practice, this assumption holds best for someone who has available space in a 457(b) plan (which accepts pre-tax contributions with its own contribution limit separate from your pension). If you aren't yet maxing out your 457(b), redirecting pension-equivalent contributions there would give you the same pre-tax treatment modeled here with this calculator. If you have no tax-advantaged space available, the personal savings option would be at a disadvantage not captured by this calculator.

**No market volatility.** The calculator uses a fixed annual return every year. Real markets fluctuate, and a string of bad years early in retirement can be far more damaging than the average return would suggest, which is a phenomenon called "sequence of returns risk."

**No mortality risk pooling.** Because everyone in a pension pool contributes together, those who live longer are subsidized by those who don't. An individual account can't replicate this, which means the pension becomes especially valuable for people who live well past average life expectancy.

**No spousal, survivor, or disability benefits.** Pensions often include options for survivor payments to a spouse, or benefits in the event of disability. These are real forms of insurance value not modeled here.

**No employer contributions.** Some personal retirement accounts include employer matching. This calculator only models the employee contribution side.

**Fixed contribution and withdrawal patterns.** Contributions are assumed to be steady throughout your career, and withdrawals are assumed to start at a fixed amount (growing with COLA). Real behavior varies.

*Real-world retirement decisions should involve a licensed financial planner who can account for your full situation. Please consult a tax professional for personalized advice.*
""")


# Input form
st.divider()
st.header("Input Assumptions")

st.info("""
**Timing Assumptions**

This calculator operates in annual periods. Within each year:
- **Contributions & deposits**: Made at the end of the year.
- **Withdrawals**: Made at the end of the year.
- **Market returns**: Earned on the balance at the *start* of the year, before that year's deposit or withdrawal.
- **COLA**: Applied to salary at the end of each working year, taking effect the following year. In retirement, applied to the pension allowance at the end of each year, taking effect the following year.
- **Step increases**: The Step 1 → Step 2 raise occurs 6 months after hire. Since the calculator uses annual periods, Year 1 contributions are averaged over 6 months at Step 1 and 6 months at Step 2. The Steps 2 → 3, 3 → 4, and 4 → 5 raises each take effect at the start of Years 3, 4, and 5 respectively.
- **Promotions**: Applied at the end of the year you specify, taking effect the following year.
""")

col1, col2, col3 = st.columns(3)
with col1:
    step_increase = st.number_input(
        "Step Increase (%)",
        value=5.5,
        min_value=0.,
        step=0.1,
        help="Annual raise from step progression (e.g., moving up a salary scale)."
    ) / 100 + 1
    starting_wage = st.number_input(
        "Starting Annual Wage ($)",
        value=120000,
        min_value=0,
        step=500,
        help="Your initial salary the first year you were hired."
    )
    work_years = st.number_input(
        "Years to Work",
        value=30,
        min_value=1,
        step=1,
        help="How many years you plan to work before retirement."
    )
with col2:
    cola_increase = st.number_input(
        "Cost of Living Adjustment (%)",
        value=3.0,
        min_value=2.5,
        max_value=5.5,
        step=0.1,
        help="Annual salary adjustment announced each October, typically between 2–3.5%."
    ) / 100 + 1
    promotion_years_input = st.text_input(
        "Promotion Years",
        value="10, 20",
        help="Year numbers in which you expect to be promoted (e.g., 10, 20). Should fall within your working years."
    )
    retirement_years = st.number_input(
        "Years After Retirement",
        value=30,
        min_value=1,
        max_value=60,
        step=1,
        help="How many years you expect to live after retiring."
    )
with col3:
    promotion_increase = st.number_input(
        "Promotion Increase (%)",
        value=10.0,
        step=1.,
        help="Salary bump when you receive a promotion."
    ) / 100 + 1
    pension_contribution_rate = st.number_input(
        "Pension Contribution Rate (%)",
        value=10.0,
        step=1.,
        help="Percentage of your salary automatically deducted and contributed to the pension system each year."
    ) / 100
    starting_allowance = st.number_input(
        "Starting Annual Pension Allowance ($)",
        value=12 * 5871.52,
        step=500.,
        help="Estimate your annual pension payout in your first year of retirement, before COLA adjustments. You can calculate yours using the RIS website pension calculator."
    )
    index_returns_rate = st.number_input(
        "Index Returns Rate (%)",
        value=7.0,
        step=0.1,
        help="Expected annual return rate of your hypothetical personal retirement investments."
    ) / 100 + 1

# Results
st.divider()
st.header("Simulation Results")

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
yearly_data = pd.DataFrame({'Year': [],
                            'Salary': [],
                            'Pension Contribution': [],
                            'Pension Contribution Total': [],
                            'Pension Redeemed': [],
                            'Pension Redeemed Total': [],
                            'Market Returns': [],
                            'Balance': []})

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
    market_returns = personal_balance * (index_returns_rate-1)
    personal_balance = personal_balance + market_returns + pension_contribution_this_year

    years.append(f"W{work_year}")
    pension_fund_values.append(0)
    personal_fund_values.append(personal_balance)
    hover_data.append([pension_contribution_this_year, 0, pension_contribution_this_year, 0, market_returns])

    # Store data for the table
    new_row = {
        "Year": f"W{work_year}",
        "Salary": f"${effective_salary:,.0f}",
        "Pension Contribution": f"${pension_contribution_this_year:,.0f}",
        "Pension Contribution Total": f"${pension_contribution_total:,.0f}",
        "Pension Redeemed": "$0",
        "Pension Redeemed Total": "$0",
        "Market Returns": f"${market_returns:,.0f}",
        "Balance": f"${personal_balance:,.0f}"
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
    market_returns = personal_balance * (index_returns_rate-1)
    personal_balance = personal_balance - pension_redeemed + market_returns

    years.append(f"R{ret_year}")
    pension_fund_values.append(pension_redeemed_total)
    personal_fund_values.append(personal_balance)
    hover_data.append([0, pension_redeemed, 0, pension_redeemed, market_returns])

    # Store data for the table
    new_row = {"Year": f"R{ret_year}",
        "Pension Contribution": "$0",
        "Pension Contribution Total": "$0",
        "Pension Redeemed": f"${pension_redeemed:,.0f}",
        "Pension Redeemed Total": f"${pension_redeemed_total:,.0f}",
        "Market Returns": f"${market_returns:,.0f}",
        "Balance": f"${personal_balance:,.0f}"
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
    name='Total Pension Received (cumulative)',
    line=dict(color='blue'),
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
    name='Personal Retirement Fund Balance',
    line=dict(color='green'),
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

# Adaptive x-axis: target ~10 labels regardless of total years, snapped to multiples of 5
total_years = len(years)
x_tick_step = max(5, int(math.ceil(total_years / 10 / 5) * 5))

# Nice y-axis interval: target ~8 gridlines, rounded to a clean magnitude
max_y = max((v for v in pension_fund_values + personal_fund_values if v is not None), default=1)
max_y = max(max_y, 1)
raw_interval = max_y / 8
magnitude = 10 ** math.floor(math.log10(raw_interval))
y_tick_interval = round(raw_interval / magnitude) * magnitude or magnitude

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

st.caption("Watch the **green line** during retirement. If it stays above zero, the personal fund wins — you got the same income as the pension and still have money left over. If it hits zero, the pension wins.")

st.plotly_chart(fig, use_container_width=True)

mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    st.metric(
        label="Pension: Total Contributed",
        value=f"${pension_contribution_total:,.0f}",
        help="The total amount automatically deducted from your paychecks and paid into the pension system over your working years."
    )
with mc2:
    st.metric(
        label="Pension: Total Received",
        value=f"${pension_redeemed_total:,.0f}",
        delta=f"${pension_redeemed_total - pension_contribution_total:,.0f} net over contributions",
        help="The total pension income paid out over all retirement years, including annual COLA increases. The delta shows how much more you received than you put in."
    )
with mc3:
    st.metric(
        label="Personal Fund: Value at Retirement",
        value=f"${personal_fund_values[work_years]:,.0f}",
        help="The balance of your hypothetical personal investment account on the day you retire, after years of contributions and market growth."
    )
with mc4:
    if personal_balance > 0:
        st.metric(
            label="Personal Fund: Balance at Death",
            value=f"${personal_balance:,.0f}",
            delta="Fund did not run out ✓",
            help="The personal fund still has money left after paying out the same income as the pension for every retirement year. This is money you'd still own at death."
        )
    else:
        st.metric(
            label="Personal Fund: Balance at Death",
            value=f"${personal_balance:,.0f}",
            delta="Fund ran out before retirement ended ✗",
            delta_color="inverse",
            help="The personal fund was depleted before your retirement years were up. The pension would have continued paying regardless."
        )

if personal_balance > 0:
    st.success(f"""
**Based on your inputs, the personal fund is viable.**

After {int(retirement_years)} years of retirement, your personal fund would still have **\\${personal_balance:,.0f}** remaining, on top of having already paid out the same income as the pension every single year. That leftover balance is money you'd still own at death. The pension would leave nothing equivalent.
""")
else:
    st.warning(f"""
**Based on your inputs, the pension wins.**

Your personal fund would have run dry before your {int(retirement_years)}-year retirement was over, while the pension would have kept paying regardless. The lifetime guarantee is the decisive advantage here; the personal fund simply can't sustain the withdrawal rate with these investment returns over this retirement length.
""")

st.markdown("""
**What each line represents:**
- The **green line** is the balance of your hypothetical personal retirement fund. Before retirement, it grows as you make contributions and earn investment returns. After retirement, you withdraw from it each year (the same amount as your pension would have paid out) and the balance either keeps growing or shrinks depending on your returns vs. withdrawal rate.
- The **blue line** is the cumulative total you've received from the pension so far. It's zero during working years, then rises steadily once retirement begins.
- The **red dashed line** marks the moment retirement begins.

**An important note on how this comparison works:** Both options pay you the *same annual income* in retirement. The personal fund withdraws the exact same amount each year as the pension would have paid. So the green line balance is what's left *on top of* having already received that income. It's the leftover, not the total.

**How to tell which option is better:**

The only question that matters is: **does the personal fund run out of money before your retirement years are up?**

- **Personal fund wins** if the green line stays above zero through all your retirement years. This means you received the same income as the pension *and* still have money left over when you die. The higher the green line at the end, the larger that leftover.
- **Pension wins** if the green line drops to zero before retirement ends. This means the personal fund ran dry, and the pension's guarantee to pay no matter how long you live is what would have kept you afloat.

The blue line (cumulative pension income) is useful context for scale, but **don't compare the green and blue lines directly** to judge a winner. They measure different things. Green is a remaining account balance; blue is a running total of income received.

**What you leave behind:**
- With the **personal fund**, whatever the green line shows at the end of your retirement is money you still own. You could leave it to heirs, donate it, or spend it.
- With the **pension**, payments stop when you die. That being said, your pension may include a *survivor benefit* (a reduced annual payment to a spouse or dependent after your death) if you choose to select that option at the time of your retirement. This calculator does not model survivor benefits.
""")

# Display the table
st.divider()
st.subheader("Year-Over-Year Breakdown")

st.markdown("""
The tables below walk through every year of your career and retirement, showing exactly where the numbers come from. Each row is one year. The left table tracks the **pension side**, and the right table tracks the **personal retirement fund side** using the same dollar amounts contributed each year.
""")

st.markdown("#### Working Years")

st.markdown("""
During your working years, a fixed percentage of your salary is contributed annually. Your salary grows each year from Cost of Living Adjustments (COLA), step increases, and any promotions.
""")

# Explanations
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
Instead of paying into the pension, imagine depositing that same amount each year into your own investment account. The column headers show the formula: **+ Deposit** (same as the pension contribution) and **+ Returns** (investment growth on your existing balance at {(index_returns_rate-1)*100:.1f}%/year) add together to produce **= Balance** at year-end.

Returns are calculated on the balance at the *start* of the year, before that year's deposit is added.
""")

# Tables
col1, col2 = st.columns(2)
with col1:
    working_pension_df = yearly_data[["Year", "Salary", "Pension Contribution", "Pension Contribution Total"]]
    working_pension_df = working_pension_df[working_pension_df['Year'].str.startswith('W')]
    working_pension_df = working_pension_df.rename(columns={
        "Pension Contribution": "Contribution",
        "Pension Contribution Total": "Total Contributed"
    })
    st.dataframe(working_pension_df, hide_index=True)

with col2:
    working_personal_df = yearly_data[["Year", "Pension Contribution", "Market Returns", "Balance"]]
    working_personal_df = working_personal_df.rename(columns={
        "Pension Contribution": "+ Deposit",
        "Market Returns": "+ Returns",
        "Balance": "= Balance"
    })
    working_personal_df = working_personal_df[working_personal_df['Year'].str.startswith('W')]
    st.dataframe(working_personal_df, hide_index=True)


st.markdown("#### Retirement Years")

st.markdown("""
Once you retire, contributions stop. The pension begins paying you a fixed annual allowance that grows each year with COLA. The personal fund is drawn down by that same amount each year, but it continues earning investment returns on whatever balance remains.
""")

# Explanations
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Pension Side**")
    st.markdown(f"""
The pension pays a set annual amount, growing by {(cola_increase-1)*100:.1f}% each year (COLA). **Pension Received** is that year's payment. **Total Received** is the running sum of all payments to date.
""")

with col2:
    st.markdown("**Personal Fund Side**")
    st.markdown(f"""
Each year, you withdraw the same dollar amount as the pension would have paid. The column headers show the formula: the previous balance earns **+ Returns** ({(index_returns_rate-1)*100:.1f}%/year), then the **− Withdrawal** is subtracted, leaving **= Balance**. If returns exceed the withdrawal, the balance grows. If not, it shrinks.
""")

# Tables
col1, col2 = st.columns(2)
with col1:
    retirement_pension_df = yearly_data[["Year", "Pension Redeemed", "Pension Redeemed Total"]]
    retirement_pension_df = retirement_pension_df.rename(columns={
        "Pension Redeemed": "Pension Received",
        "Pension Redeemed Total": "Total Received"
    })
    retirement_pension_df = retirement_pension_df[retirement_pension_df['Year'].str.startswith('R')]
    st.dataframe(retirement_pension_df, hide_index=True)

with col2:
    retirement_personal_df = yearly_data[["Year", "Pension Redeemed", "Market Returns", "Balance"]]
    retirement_personal_df = retirement_personal_df.rename(columns={
        "Pension Redeemed": "− Withdrawal",
        "Market Returns": "+ Returns",
        "Balance": "= Balance"
    })
    retirement_personal_df = retirement_personal_df[retirement_personal_df['Year'].str.startswith('R')]
    st.dataframe(retirement_personal_df, hide_index=True)


# Case Studies
st.divider()
st.header("Case Studies")

st.markdown("""
The two examples below show one scenario where each option wins. To see the full charts and tables for either, enter the listed settings into the calculator above.
""")

with st.expander("Case Study A — Personal Fund Wins"):
    st.markdown("""
**Settings:** Starting wage \\$120,000 · Step increase 5.5% · COLA 3% · Promotions at years 10 and 20 (10% each) · Pension contribution rate 10% · Index returns 7% · Work years 30 · Retirement years 30 · First-year pension allowance \\$70,458

---

Alice is a public school administrator who earns \\$120,000 to start. Over her 30-year career, her salary grows steadily through step increases, COLA adjustments, and two promotions. Each year, 10% of her salary goes into the pension.

**The pension:** By retirement, Alice has paid roughly **\\$785,000** into the pension over 30 years. In exchange, she receives an allowance starting at about \\$70,458 per year, growing 3% annually. Over 30 years of retirement, her total pension payments add up to roughly **\\$3.35 million**.

**The personal fund:** If Alice had deposited those same contributions into an account earning 7% per year, she would have built up roughly **\\$2.02 million by retirement**. She withdraws the same amount as her pension would have paid each year. Because her 7% returns exceed her withdrawal rate, her account keeps growing even in retirement, ending at over **\\$6.28 million**.

**Verdict:** The personal fund wins. Here's why: both options paid Alice the exact same annual income throughout retirement. The pension didn't give her more — they were identical year by year. But the personal fund ended with \\$6.28 million still in the account, money she owns outright and can leave to her family. The pension leaves nothing at death.

This is also the case that most commonly causes confusion. People look at "\\$3.35 million in pension income" and think the pension came out ahead — but that figure is the cumulative total of Alice's annual payments, and the personal fund paid out the exact same cumulative amount. The \\$6.28 million is the bonus on top of that.
""")

with st.expander("Case Study B — Pension Wins"):
    st.markdown("""
**Settings:** Starting wage \\$65,000 · Step increase 5.5% · COLA 3% · No promotions · Pension contribution rate 10% · Index returns 5% · Work years 20 · Retirement years 40 · First-year pension allowance \\$27,000

---

Bob is a civil servant who starts at \\$65,000 and works a steady 20-year career without promotions. He retires relatively early and lives a long life of 40 years in retirement. The stock market delivers modest returns of about 5% per year over his lifetime.

**The pension:** Over 20 years of work, Bob contributes roughly **\\$175,000** to the pension. In retirement, he receives about \\$27,000 in year one, growing 3% annually. Over 40 years, that adds up to approximately **\\$2 million** in total pension income — more than 11 times what he put in.

**The personal fund:** Bob's 20 years of contributions at 5% annual returns would have grown to roughly **\\$265,000 by retirement**. Once he begins withdrawing \\$27,000 per year (growing 3% annually), his investment growth cannot keep pace with the withdrawals. His personal fund is **depleted within about 13 years**, leaving him with nothing for the remaining 27 years of retirement.

**Verdict:** The pension wins. Bob's personal fund runs out before his retirement does. At 5% returns, the growth simply isn't enough to sustain 40 years of withdrawals from a \\$265,000 starting balance. The pension's guarantee — that it pays no matter how long he lives — is exactly what he needs here. Without it, he runs out of money in his early 70s.

The pension tends to win when returns are modest, the retirement is long, or the fund doesn't have enough time to grow during working years. The lifetime guarantee is the thing a personal account cannot replicate.
""")
