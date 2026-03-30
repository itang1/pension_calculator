import streamlit as st
import pandas as pd
from plotly import graph_objects as go


st.title("Pension vs. Personal Savings Calculator")

st.markdown("""
This calculator helps you compare two different ways of saving for retirement. Many public employees — teachers, law enforcement officers, civil servants — are required to contribute a portion of every paycheck into a pension plan. The question this tool tries to answer is simple: **what if you had kept that money and invested it yourself instead?**
""")

col_a, col_b = st.columns(2)
with col_a:
    st.info("""
**Traditional Pension**

Each year, a fixed percentage of your paycheck (e.g. 10%) is automatically deducted and paid into the pension system. You don't control this money or decide how it's invested. In exchange, when you retire, the pension pays you a guaranteed fixed amount every year for the rest of your life — no matter how long you live or how the stock market performs.
""")
with col_b:
    st.info("""
**Hypothetical Personal Retirement Account**

This calculator asks: what if, instead of contributing to the pension, you had deposited that same amount each year into your own investment account (like a 403(b) or 457(b))? Your money would grow over time through market returns. After retiring, you would withdraw the same annual amount as your pension allowance would have been — and whatever is left over keeps growing.
""")

st.markdown("""
By running both scenarios side by side with the same inputs, you can see which approach might leave you better off — and under what conditions.
""")

st.divider()

with st.expander("Background: Why This Calculator Exists"):
    st.markdown("""
    ### The Question Behind This Tool

    If you work in the public sector, you probably didn't choose to participate in a pension — it was mandatory. A fixed slice of every paycheck has gone into the pension system, whether you thought it was a good deal or not. And at some point, you might have asked yourself: *is this actually worth it? Would I have been better off just investing that money myself?*

    That question is harder to answer than it sounds. The pension provides something genuinely valuable: a guaranteed income that lasts as long as you do, regardless of market conditions. But the money you put in is gone — you can't pass it on, you can't access it early, and you have no control over it. Meanwhile, a personal investment account gives you full ownership. If your investments do well, you can end up with far more. If you die early, your heirs inherit the balance. But if your investments underperform, or you live longer than expected, you could run short.

    This tool was built to take some of the guesswork out of that comparison. By plugging in your own salary, contribution rate, expected investment return, and retirement timeline, you can see a data-driven side-by-side estimate of how the two paths compare for your specific situation.

    ---

    ### What the Research and Debate Says

    Pension systems were designed for a different era. When life expectancy was shorter and most people stayed in the same job for decades, a defined-benefit pension made enormous sense. Today, with people living longer, changing jobs more frequently, and having access to low-cost index funds, the calculus is less clear.

    Critics of pensions argue that they are financially unsustainable — many public pension funds are underfunded, meaning they owe more in future benefits than they currently hold in assets. Taxpayers ultimately bear the risk of covering those gaps. Critics also argue that the pension structure disproportionately rewards long-tenured employees at the expense of those who leave before vesting, and that the lack of portability is a serious drawback in a world where people change careers.

    Defenders of pensions counter that guaranteed income in retirement is a powerful protection against poverty — especially for workers who might not otherwise save enough, or who lack the financial knowledge to manage their own investments. They also note that public sector workers often earn less than their private sector counterparts, and the pension is part of how that gap is compensated.

    Both sides have a point. The honest answer is: *it depends.* It depends on how long you work, how long you live, what the market does, and what you value.

    ---

    ### What This Calculator Does Not Account For — And Why It Matters

    One important factor this tool simplifies is **taxes**. In reality, pension contributions come out of your paycheck before taxes are applied — meaning you don't pay income tax on that money now (you pay later, when you receive your pension payments in retirement). This is a meaningful benefit.

    By contrast, if you tried to save that same amount yourself in a taxable brokerage account, you'd be investing after-tax dollars — money you've already paid income tax on. That puts the personal savings scenario at a disadvantage that this calculator does not model.

    However, there is an important counterpoint: many public employees have access to a **457(b) deferred compensation plan**, which is a tax-advantaged retirement account with its own separate contribution limit (currently $24,500/year as of 2026, and separate from your pension). If you are already maxing out your 457(b), then the pension contribution is genuinely competing with after-tax savings — because there is no additional tax-sheltered space to redirect it. In that scenario, the tax advantage of the pension becomes more significant.

    If you are *not* maxing out your 457(b), the comparison is more nuanced: you could theoretically redirect the pension contribution into your 457(b) and still enjoy pre-tax treatment, which would make the personal fund scenario more competitive than this calculator suggests.

    **Bottom line on taxes:** This calculator treats both options as if taxes don't exist. In practice, the pension has a tax advantage — but how much that matters depends on your individual situation, whether you're already maxing your 457(b), and what tax bracket you're in during retirement. This is one of the reasons this tool is a starting point, not a final answer.
    """)

with st.expander("Limitations of This Tool"):
    st.markdown("""
    This calculator is intended as an educational and exploratory tool. It is not a comprehensive actuarial model, nor does it account for all variables involved in retirement planning. Specifically:

    - **No tax modeling.** Pension contributions are pre-tax; personal savings may be post-tax depending on your situation. See the background essay above for details.
    - **No market volatility.** The calculator assumes a fixed annual return every year. Real markets go up and down, and a bad sequence of returns early in retirement can have an outsized negative effect on a personal fund — even if the long-run average is the same.
    - **No mortality risk pooling.** Pensions are designed so that people who live longer effectively subsidize people who don't. If you live well past average life expectancy, the pension becomes an especially good deal — and vice versa.
    - **No spousal, survivor, or disability benefits.** Most pension systems offer options like survivor benefits for a spouse or payments in the event of disability. These are real forms of insurance value that are not modeled here.
    - **No employer matching.** Some personal retirement accounts include employer contributions. This calculator only models the employee contribution side.
    - **Fixed contribution patterns.** The calculator assumes you contribute steadily every year and withdraw a set amount in retirement. Real behavior varies.

    This tool is meant to support transparent, data-informed comparisons. Real-world retirement decisions should involve a licensed financial planner who can account for your full situation.
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

st.markdown("""
The three case studies below illustrate how the outcome can swing dramatically depending on your assumptions. Try plugging each set of inputs into the calculator above to see the charts and full year-by-year breakdown for yourself.
""")

with st.expander("Case Study A — It's Complicated"):
    st.markdown("""
    **Settings to enter:**
    Starting wage: $120,000 · Step increase: 5.5% · COLA: 3% · Promotion increase: 10% · Promotion years: 10, 20 · Pension contribution rate: 10% · Index returns: 7% · Work years: 30 · Retirement years: 30 · First-year pension allowance: $70,458.24

    ---

    Alice is a public school administrator who earns $120,000 to start. Over her 30-year career, her salary grows steadily through step increases, annual cost-of-living adjustments, and two promotions. Each year, 10% of her salary goes into the pension — money she never sees or invests herself.

    **What the pension gives her:** By retirement, Alice has paid roughly **$785,000** into the pension system over 30 years. In exchange, she receives a pension allowance that starts at about $70,458 per year — and grows by 3% every year to keep pace with inflation. Over 30 years of retirement, her total pension income adds up to roughly **$3.35 million**. That's more than four times what she put in.

    **What a personal fund would have looked like:** If Alice had instead deposited those same annual contributions into her own investment account earning 7% per year, she would have built up roughly **$2.02 million by retirement**. She would then withdraw her pension-equivalent amount each year. Because her investment returns (7%) comfortably exceed her withdrawal rate, her account keeps growing even in retirement — ending up at over **$6.28 million** by the end of her 30-year retirement.

    **Verdict:** This is the most common and interesting scenario — there's no clean winner. The pension pays out more total income over the course of retirement ($3.35M vs. the $2.02M the personal fund held at the time of retirement). But the personal fund ends with a dramatically larger balance ($6.28M) that Alice could pass on to her family or use however she chooses. The pension stops when she dies.

    *This case illustrates the core trade-off: guaranteed income for life vs. ownership, flexibility, and wealth transfer.*
    """)

with st.expander("Case Study B — Pension Wins"):
    st.markdown("""
    **Settings to enter:**
    Starting wage: $65,000 · Step increase: 5.5% · COLA: 3% · Promotion increase: 10% · Promotion years: *(leave blank)* · Pension contribution rate: 10% · Index returns: 5% · Work years: 20 · Retirement years: 40 · First-year pension allowance: $27,000

    ---

    Bob is a civil servant who starts at $65,000 and works a steady 20-year career without promotions. He retires at a relatively young age and lives a long life — 40 years in retirement. The stock market during his lifetime delivers modest but not spectacular returns of about 5% per year.

    **What the pension gives him:** Over 20 years of work, Bob contributes roughly **$175,000** to the pension. In retirement, he receives about $27,000 in his first year, growing by 3% annually. Over 40 years, that adds up to approximately **$2 million** in total pension income — more than 11 times what he put in.

    **What a personal fund would have looked like:** Bob's 20 working years of contributions at 5% annual returns would have grown to roughly **$265,000 by retirement**. In retirement, he begins withdrawing $27,000 per year (growing 3% annually with COLA). At 5% returns, his investment growth cannot keep pace with his withdrawals. His personal fund is **depleted within about 13 years** — leaving him with nothing for the final 27 years of retirement.

    **Verdict:** The pension wins decisively. Bob lives too long and earns too little on his investments for the personal fund to sustain him. The pension's guarantee — that it pays no matter how long he lives — is exactly the protection he needs. Without it, he runs out of money in his mid-70s.

    *This case illustrates why pensions are particularly valuable for people who live long lives, retire early, or are in a low-return market environment. The pension's "mortality pooling" — where everyone's contributions collectively fund benefits for those who live longest — is a feature that a personal account simply cannot replicate.*
    """)

with st.expander("Case Study C — Personal Fund Wins"):
    st.markdown("""
    **Settings to enter:**
    Starting wage: $150,000 · Step increase: 5.5% · COLA: 3% · Promotion increase: 10% · Promotion years: 15, 25 · Pension contribution rate: 10% · Index returns: 9% · Work years: 35 · Retirement years: 20 · First-year pension allowance: $120,000

    ---

    Carol is a senior public official who earns $150,000 to start, receives two promotions over a 35-year career, and retires with a generous pension allowance. She is financially sophisticated, invests in a diversified index fund portfolio, and benefits from a strong long-run market — averaging about 9% annually. She plans conservatively for 20 years in retirement.

    **What the pension gives her:** Carol contributes roughly **$1.4 million** to the pension over her career. In retirement, she receives approximately $120,000 in the first year, growing 3% annually. Over 20 years, her total pension income is roughly **$3.2 million**.

    **What a personal fund would have looked like:** Carol's 35 years of contributions growing at 9% annually compound dramatically — she would have accumulated roughly **$5.5 million by retirement**. Even after withdrawing $120,000+ per year in retirement, her 9% annual returns far exceed what she's taking out. Her fund continues growing throughout retirement, ending at well over **$18 million**.

    **Verdict:** The personal fund wins by a wide margin. Carol's high salary means her contributions are large in dollar terms, and 9% compounding over 35 years creates an enormous amount of wealth. The pension's $3.2M total payout looks modest by comparison — and she has nothing left to show for it at the end, while her personal fund leaves a multi-million dollar estate.

    *This case illustrates why the personal fund is often the better choice for high earners with long careers in strong market conditions — especially those who want to build generational wealth or have heirs they want to provide for. However, it relies on favorable market returns that are not guaranteed.*
    """)
