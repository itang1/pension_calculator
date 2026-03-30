import streamlit as st
import pandas as pd
from plotly import graph_objects as go


st.title("Pension vs. Personal Savings Calculator")

st.divider()

with st.expander("What This Calculator Does"):
    st.markdown("""
    This calculator helps you compare two different ways of saving for retirement:

    - **Traditional Pension**
        - Each year, a portion of your paycheck (e.g. 10%) goes into a pension plan.
        - When you retire, you receive back a set amount of money (i.e. your **pension allowance**) every month or year for as long as you live.
        - This calculator adds up how much you'd get from the pension over your retirement years.

    - **Personal Retirement Account** - Like a 457(b), 403(b), or 401(k)
        - Imagine if, instead of paying into the pension, you invested that same amount of money each year in your own personal retirement account.
        - Your money grows over time through investment returns based on the stock market.
        - After you retire, you take out the same yearly amount as the pension allowance you would've had.
        - Any leftover money keeps growing (or shrinking) every year based on the stock market.

    By comparing these two options side by side, you can see which one might give you more money over time, based on factors like salary, number of years you expect to work, and how long you expect to be retired.
""")

with st.expander("The Public Pension Debate"):
    st.markdown("""
    Many public sector employees (such as teachers, law enforcement officers, and civil servants) mandatorily participate in defined-benefit pension plans. Under a pension plan, workers are required to contribute a fixed percentage of their salary throughout their working years in exchange for a guaranteed, fixed income during their retirement years. The employer bears the responsibility of paying out the pension and assumes the investment risk. By contrast, the private sector has largely shifted to defined-contribution plans such as 401(k)s and 403(b)s. In these plans, employees can voluntarily invest contributions into a range of market assets, often with some employer matching as well. Since market performance is not guaranteed, employees assume the full responsibility for managing the risks associated with their retirement investments.

    This structural difference between the two retirement systems has sparked debate and, at times, resentment and jealousy. Critics argue that pensions are financially unsustainable in the long run, especially as populations age and life expectancy increases. They contend that pensions impose an unfair burden on taxpayers, particularly in states or cities where the government pension plan is underfunded yet still obligated to conjure up funds to pay out the promised benefits. Some detractors even feel that pension benefits are overly generous compared to what private sector employees receive. On the other hand, proponents maintain that pensions encourage individuals to accept public sector jobs, which can sometimes pay less than their equivalent private sector counterparts. They also highlight that pensions help reduce elderly poverty through predictable monthly or annual payments—especially benefiting those who might not otherwise save enough or those who lack the financial literacy to manage retirement funds effectively. Ultimately, this debate involves issues of fairness, fiscal responsibility, and the government's role in securing citizens' retirement income.

    While pensions indeed offer stability and predictability, they might not be the optimal choice for everyone—particularly for those who are disciplined, financially literate, and value the flexibility, control, and potential upside of tax-deferred personal accounts. This calculator is designed to explore the question that follows: **If the same annual contribution were made, would a traditional pension or a personal investment account yield a better outcome?**

    This interactive financial modeling tool allows users to model variables such as salary growth, expected investment returns, and number of years spent in retirement. It offers a **data-driven** comparison between the long-term value of a pension vs. a hypothetical self-managed investment strategy. The goal of this calculator is to support **evidence-based dialogue** so that individuals can form fact-based opinions and make informed decisions rather than rely on emotional arguments or misinformation.
    """)

with st.expander("What This Tool Is Not"):
    st.markdown("""
    This calculator is intended as an educational and exploratory tool. It is not a comprehensive actuarial model, nor does it account for all variables involved in retirement planning. Specifically:

    - It does not incorporate mortality risk pooling, which can make pensions more or less valuable for those who do not live the average life expectancy.
    - It excludes spousal benefits, survivor options, or disability protections often built into pension systems.
    - It assumes consistent contributions and withdrawal patterns, and does not simulate market volatility, behavioral investing patterns, or tax implications.
    - It does not predict or advise on individual financial outcomes and should not be used in place of professional financial advice.

    This tool is meant to support transparent, data-informed comparisons, but real-world retirement decisions should consider institutional rules, legal constraints, personal risk tolerance, and long-term goals.
    """)


# Input form
st.divider()
st.header("Input variable assumptions")
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
        help="Your initial salary the year you were hired."
    )
    work_years = st.number_input(
        "Years to Work",
        value=30,
        min_value=1,
        step=1,
        help="Number of years you plan to work before retirement."
    )
with col2:
    cola_increase = st.number_input(
        "Cost of Living Adjustment (%)",
        value=3.0,
        min_value=2.5,
        max_value=5.5,
        step=0.1,
        help="Annual salary adjustment announced each October, typically between 2–5%."
    ) / 100 + 1
    promotion_years_input = st.text_input(
        "Promotion Years",
        value="10, 20",
        help="Years in which you expect to be promoted (e.g., 10, 20). Should fall within your working years."
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
        help="Annual return rate of your personal retirement investments (e.g., 403b)."
    ) / 100 + 1

st.info("""
**Timing Assumptions**

This calculator operates in annual periods. Within each year:
- **Contributions & deposits**: made at the end of the year.
- **Withdrawals**: made at the end of the year.
- **Market returns**: earned on the balance at the *start* of the year — before that year's deposit or withdrawal.
- **COLA**: applied to salary at the end of each working year, taking effect the following year. In retirement, applied to the pension allowance at the end of each year, taking effect the following year.
- **Step increases**: The Step 1 → Step 2 raise occurs 6 months after hire. Since the calculator uses annual periods, Year 1 contributions are averaged over 6 months at Step 1 and 6 months at Step 2. Steps 2 → 3, 3 → 4, and 4 → 5 each take one full year and take effect at the start of Years 2, 3, and 4 respectively.
- **Promotions**: applied at the end of the year you specify, taking effect the following year.
""")

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

    # Store data for the table
    new_row = {
        "Year": f"W{work_year}",
        "Salary": f"${effective_salary:,.0f}",
        "Pension Contribution": f"${pension_contribution_this_year:,.0f}",
        "Pension Contribution Total": f"${pension_contribution_total:,.0f}",
        "Pension Redeemed": "$0",  # No pension redeemed during work years
        "Pension Redeemed Total": "$0",  # No pension redeemed during work years
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

    # Store data for the table
    new_row = {"Year": f"R{ret_year}",
        "Pension Contribution": "$0",  # No pension contribution paid during retirement years
        "Pension Contribution Total": "$0",  # No pension contribution paid during retirement years
        "Pension Redeemed": f"${pension_redeemed:,.0f}",
        "Pension Redeemed Total": f"${pension_redeemed_total:,.0f}",
        "Market Returns": f"${market_returns:,.0f}",
        "Balance": f"${personal_balance:,.0f}"
    }
    yearly_data = pd.concat([yearly_data, pd.DataFrame([new_row])], ignore_index=True)

    # Update allowance for next year
    pension_redeemed *= cola_increase

# Chart explanation
st.markdown("""
The chart below shows how both options — the **pension** and the **personal retirement fund** — compare over your entire career and retirement.

- The **green line** shows the value of your hypothetical personal retirement fund. During your working years, it grows as you make annual contributions and earn investment returns. During retirement, you withdraw from it each year to cover living expenses. The line will rise or fall depending on whether your investment returns outpace your withdrawals.
- The **blue line** shows the total amount of money you've received from your pension. It's zero during your working years (the pension hasn't paid out yet), then rises steadily once you retire as you collect your annual allowance.
- The **red dashed line** marks the year you retire — where your working years end and your retirement years begin.

**How to read this chart:** Before the red line, watch the green line climb — that's your personal fund growing. After the red line, the blue line starts rising (your pension paying out), and the green line either keeps growing or starts declining depending on how well your investments do. The higher the green line is at the end, the more money is left over in your personal fund.
""")

# Plot
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=years,
    y=pension_fund_values,
    mode='lines+markers',
    name='Total Pension Received (cumulative)',
    line=dict(color='blue'),
    hovertemplate='Year: %{x}<br>Total pension received: $%{y:,.0f}<extra></extra>'
))

fig.add_trace(go.Scatter(
    x=years,
    y=personal_fund_values,
    mode='lines+markers',
    name='Personal Retirement Fund Balance',
    line=dict(color='green'),
    hovertemplate='Year: %{x}<br>Personal fund balance: $%{y:,.0f}<extra></extra>'
))

fig.update_layout(
    title='Pension vs. Personal Retirement Fund Over Time',
    xaxis_title='Year (W = Working, R = Retirement)',
    yaxis_title='Dollar Amount ($)',
    xaxis=dict(
        tickangle=45,
        tickmode='array',
        tickvals=[years[i] for i in range(0, len(years), 5)],
        tickfont=dict(size=10)
    ),
    yaxis=dict(
        gridcolor='lightgray',
        tickformat=',',
        separatethousands=True
    ),
    plot_bgcolor='white',
    legend=dict(x=0.01, y=0.99),
    margin=dict(l=40, r=20, t=60, b=100)
)

fig.add_vline(x=work_years, line_width=3, line_dash="dash", line_color="red", annotation_text="Retirement begins here",
          annotation_position="top right")
tick_interval = max(pension_contribution_total, pension_redeemed_total, personal_balance)//10
fig.update_yaxes(showgrid=True, dtick=tick_interval)
fig.update_xaxes(showgrid=True)

st.plotly_chart(fig, use_container_width=True)

# Results Section
st.divider()
st.subheader("Summary")

st.markdown(f"**Total Pension Contributions:** ${pension_contribution_total:,.0f}", help="The total amount automatically deducted from your paychecks and contributed to the pension system over the course of your working years.")
st.markdown(f"**Total Pension Received:** ${pension_redeemed_total:,.0f}", help="The total amount you received from the pension disbursements based on your retirement allowance throughout your retirement years, accounting for Cost of Living Adjustments.")
st.markdown(f"**Personal Fund Value at Retirement:** ${personal_fund_values[work_years]:,.0f}", help="The total value accumulated in your hypothetical personal retirement fund by the time you retire. It includes your annual contributions as well as the growth of those contributions through market returns.")
st.markdown(f"**Personal Fund Value at End of Retirement:** ${personal_balance:,.0f}", help="The remaining balance in your hypothetical personal retirement fund after you've withdrawn your annual allowance for each year of retirement.")

# Display the table
st.divider()
st.subheader("Year Over Year Breakdown")

st.markdown("""
The tables below walk through every year of your career and retirement, showing exactly where the numbers come from. Each row is one year. The left table tracks the **pension side**, and the right table tracks the **personal retirement fund side** — using the same contribution amounts so the comparison is apples-to-apples.
""")

st.markdown("#### Working Years")

st.markdown("""
During your working years, a fixed percentage of your salary is contributed each year — either into the pension system, or (hypothetically) into your own personal investment account. Your salary grows each year from Cost of Living Adjustments (COLA), step increases, and any promotions you receive.
""")

# Explanations
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Pension Contributions**")
    st.markdown(f"""
Each year, {pension_contribution_rate*100:.0f}% of your salary is automatically contributed to the pension system. You don't get to keep or invest this money — it goes into the pension pool.

- **Salary** grows each year by your COLA ({(cola_increase-1)*100:.1f}%). In your first 4 years, it also grows by your step increase ({(step_increase-1)*100:.1f}%). In promotion years ({str(promotion_years).strip("[]") if promotion_years else "none entered"}), it gets an additional {(promotion_increase-1)*100:.0f}% bump. *(Special case: Year 1 averages your Step 1 and Step 2 salaries, since the Step 1→2 raise happens 6 months into the job.)*
- **Pension Contribution** is {pension_contribution_rate*100:.0f}% of that year's salary — the amount deducted from your paycheck.
- **Pension Contribution Total** is a running tally of everything you've contributed so far across all working years.
    """)

with col2:
    st.markdown("**Hypothetical Personal Fund**")
    st.markdown(f"""
Instead of paying into the pension, imagine you deposited that same amount into your own investment account (like a 403b or 401k) each year. Your money would grow through investment returns.

- **Deposit** is the same dollar amount as your pension contribution that year — the comparison is kept equal so it's fair.
- **Market Returns** is the growth your existing balance earned that year, based on a {(index_returns_rate-1)*100:.1f}% annual return. *(Returns are calculated on the balance at the start of the year, before that year's deposit is added.)*
- **Balance** is what your account is worth at the end of the year: last year's balance, plus market returns, plus this year's deposit.
    """)


# Tables
col1, col2 = st.columns(2)
with col1:
    working_pension_df = yearly_data[["Year", "Salary", "Pension Contribution", "Pension Contribution Total"]]
    working_pension_df = working_pension_df[working_pension_df['Year'].str.startswith('W')]
    st.dataframe(working_pension_df, hide_index=True)

with col2:
    working_personal_df = yearly_data[["Year", "Pension Contribution", "Market Returns", "Balance"]]
    working_personal_df = working_personal_df.rename(columns={"Pension Contribution": "Deposit"})
    working_personal_df = working_personal_df[working_personal_df['Year'].str.startswith('W')]
    st.dataframe(working_personal_df, hide_index=True)


st.markdown("#### Retirement Years")

st.markdown("""
Once you retire, you stop contributing to either account. The pension begins paying you a fixed annual allowance (which increases each year with COLA). The personal fund is drawn down by that same amount each year — but it continues to earn investment returns on whatever is left.
""")

# Explanations
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Pension Disbursements**")
    st.markdown(f"""
The pension pays you a set amount every year for the rest of your life. That amount increases slightly each year to keep up with inflation (COLA).

- **Pension Received** is the amount paid to you that year. It increases each year by {(cola_increase-1)*100:.1f}% (COLA).
- **Pension Received Total** is a running tally of all pension payments you've received so far across retirement.
    """)

with col2:
    st.markdown("**Hypothetical Personal Fund**")
    st.markdown(f"""
Your personal fund keeps earning returns even in retirement. Each year, you withdraw the same amount as the pension would have paid — then your remaining balance earns market returns.

- **Withdrawn** is the same dollar amount as the pension payout that year — keeping the comparison fair.
- **Market Returns** is the growth earned on your remaining balance before the withdrawal, at a {(index_returns_rate-1)*100:.1f}% annual return.
- **Balance** is what's left at the end of the year: last year's balance, plus market returns, minus the withdrawal. If your returns exceed your withdrawal, the balance grows. If not, it shrinks.
    """)



# Tables
col1, col2 = st.columns(2)
with col1:
    retirement_pension_df = yearly_data[["Year", "Pension Redeemed", "Pension Redeemed Total"]]
    retirement_pension_df = retirement_pension_df.rename(columns={"Pension Redeemed": "Pension Received", "Pension Redeemed Total": "Pension Received Total"})
    retirement_pension_df = retirement_pension_df[retirement_pension_df['Year'].str.startswith('R')]
    st.dataframe(retirement_pension_df, hide_index=True)

with col2:
    retirement_personal_df = yearly_data[["Year", "Pension Redeemed", "Market Returns", "Balance"]]
    retirement_personal_df = retirement_personal_df.rename(columns={"Pension Redeemed": "Withdrawn"})
    retirement_personal_df = retirement_personal_df[retirement_personal_df['Year'].str.startswith('R')]
    st.dataframe(retirement_personal_df, hide_index=True)


# Case Studies
st.divider()
st.header("Case Studies")

with st.expander("Case Study A"):
    st.markdown("""
        Alice's starting annual wage is $120,000. She assumes a standard step increase of 5.50%, COLA of 3%, promotion increase of 10%, pension contribution rate of 10%, and index returns rate of 7%. She receives a promotion in years 10 and 20. She works 30 years and expects to live 30 years in retirement. Her estimated first-year annual pension allowance is $70,458.24.

        According to the calculator, by the end of Alice's 30 working years, she will have contributed about $785k to the pension system. If she had instead deposited that same amount into a tax-advantaged personal retirement fund, she would have accumulated over $2.02M by retirement. Over her 30 years of retirement, she will receive over $3.35M in total pension allowance (accounting for annual COLA increases). This substantially exceeds both her $785k in contributions and the $2.02M she would have accumulated in a personal fund by retirement.

        However, the key difference between the two options appears at the end of retirement: with the personal fund, Alice would have a remaining balance of over $6.28M to keep or leave to whomever she wishes. With the pension, the payments stop at death — the only remaining value is whatever survivor benefit she elected when she left the pension system.

        Under these assumptions, the pension pays out more total income over retirement, but the personal fund leaves a substantial estate. Which option is "better" depends on individual priorities: guaranteed lifetime income versus flexibility and wealth transfer.
    """)
