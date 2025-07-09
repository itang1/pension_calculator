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
    Many public sector employees (such as teachers, law enforcement officers, and civil servants) mandatorily participate in defined-benefit pension plans. Under a pension plan, workers are required to contribute a fixed percentage of their salary throughout their working years in exchange for a guaranteed, fixed income during their retirement years. The employer bears the responsibility of paying out the pension and assumes the investment risk. By contrast, the private sector has largely shifted to defined-contribution plans such as 401(k)s and 403(b)s. In these plans, employees can voluntarily invest contributions into a range of market assets, often with some employer matching as well. Since market performance is not guaranteed, employees assume the full responsibility for managing the risks associated with thier retirement investments.

    This structural difference between the two retirement systems has sparked debate and, at times, resentment and jealousy. Critics argue that pensions are financially unsustainable in the long run, especially as populations age and life expectancy increases. They contend that pensions impose an unfair burden on taxpayers, particularly in states or cities where the government pension plan is underfunded yet still obligated to conjure up funds to pay out the promised benefits. Some detractors even feel that pension benefits are overly generous compared to what private sector employees receive. On the other hand, proponents maintain that pensions encourage individuals to accept public sector jobs, which can sometimes pay less than their equivalent private sector counterparts. They also highlight that pensions help reduce elderly poverty through predictable monthly or annual payments—especially benefiting those who might not otherwise save enough or those who lack the financial literacy to manage retirement funds effectively. Ultimately, this debate involves issues of fairness, fiscal responsibility, and the government’s role in securing citizens’ retirement income.

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
    pension_tax_rate = st.number_input(
        "Pension Tax Rate (%)",
        value=10.0,
        step=1.,
        help="Percentage of your salary contributed to the pension system each year."
    ) / 100
    starting_allowance = st.number_input(
        "Annual Pension Allowance ($)",
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



# Results
st.divider()
st.header("Simulation Results")

# Parse promotion years
try:
    promotion_years = [int(y.strip()) for y in promotion_years_input.split(",") if y.strip().isdigit()]
except:
    promotion_years = []

# Initialize variables
pension_tax_paid = 0
pension_redeemed = 0
personal_retirement_fund = 0
current_wage = starting_wage
current_allowance = starting_allowance

# Tracking for visualization
years = ["W0"]
pension_fund_values = [0]
personal_fund_values = [0]
yearly_data = pd.DataFrame({'Year': [],
                            'Pension Tax Paid': [],
                            'Pension Redeemed': [],
                            'Personal Fund Value': []})

# Work phase - Loop through the work years
for work_year in range(1, int(work_years) + 1):
    pension_tax_paid += current_wage * pension_tax_rate
    personal_retirement_fund = (personal_retirement_fund * index_returns_rate) + current_wage * pension_tax_rate

    years.append(f"W{work_year}")
    pension_fund_values.append(0)
    personal_fund_values.append(personal_retirement_fund)

    # Store data for the table
    new_row = {
        "Year": f"W{work_year}",
        "Pension Tax Paid": f"${pension_tax_paid:,.0f}",
        "Pension Redeemed": "$0",  # No pension redeemed during work years
        "Personal Fund Value": f"${personal_retirement_fund:,.0f}"
    }
    yearly_data = pd.concat([yearly_data, pd.DataFrame([new_row])], ignore_index=True)

    # Update salary for next year
    current_wage *= cola_increase
    if 2 <= work_year <= 5:
        current_wage *= step_increase
    if work_year in promotion_years:
        current_wage *= promotion_increase

# Retirement phase - Loop through the retirement years
for ret_year in range(1, retirement_years + 1):
    pension_redeemed += current_allowance
    personal_retirement_fund = (personal_retirement_fund - current_allowance) * index_returns_rate

    years.append(f"R{ret_year}")
    pension_fund_values.append(pension_redeemed)
    personal_fund_values.append(personal_retirement_fund)

    # Store data for the table
    new_row = {"Year": f"R{ret_year}",
        "Pension Tax Paid": "$0",  # No pension tax paid during retirement years
        "Pension Redeemed": f"${pension_redeemed:,.0f}",
        "Personal Fund Value": f"${personal_retirement_fund:,.0f}"
    }
    yearly_data = pd.concat([yearly_data, pd.DataFrame([new_row])], ignore_index=True)

    # Update allowance for next year
    current_allowance *= cola_increase

# Plot
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=years,
    y=pension_fund_values,
    mode='lines+markers',
    name='Pension Redeemed',
    line=dict(color='blue')
))

fig.add_trace(go.Scatter(
    x=years,
    y=personal_fund_values,
    mode='lines+markers',
    name='Hypothetical Personal Retirement Fund',
    line=dict(color='green')
))

fig.update_layout(
    title='Retirement Fund Comparison',
    xaxis_title='Year',
    yaxis_title='Amount ($)',
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

fig.add_vline(x=work_years, line_width=3, line_dash="dash", line_color="red", annotation_text="Year of Retirement",
          annotation_position="top right")
tick_interval = max(pension_tax_paid, pension_redeemed, personal_retirement_fund)//10
fig.update_yaxes(showgrid=True, dtick=tick_interval)
fig.update_xaxes(showgrid=True)

st.plotly_chart(fig, use_container_width=True)

# Results Section
st.divider()
st.subheader("Summary")

st.write(f"**Total Pension Tax Paid:** ${pension_tax_paid:,.0f}")
st.write("The total amount you paid into the pension system through automatic deductions over the course of your working years.")

st.write(f"**Total Pension Redeemed:** ${pension_redeemed:,.0f}")
st.write("The total amount you received from the pension disbursements based on your retirement allowance throughout your retirement years, accounting for Cost of Living Adjustments.")

st.write(f"**Personal Fund Value at Retirement:** ${personal_fund_values[work_years]:,.0f}")
st.write("The total value accumulated in your hypothetical personal retirement fund by the time you retire. It includes your annual contributions as well as the growth of those contributions through market returns.")

st.write(f"**Personal Fund Value at Death:** ${personal_retirement_fund:,.0f}")
st.write("The remaining balance in your hypothetical personal retirement fund after you’ve withdrawn your annual allowance for each year of retirement.")

# Display the table
st.divider()
st.subheader("Year Over Year Breakdown")
st.write("**Cumulative summation**")
st.dataframe(yearly_data, hide_index=True)

# Explain math
st.divider()
st.subheader("How the Math Works")
st.markdown(f"""
    This calculator models the working years followed by the retirement years.

    **Working Years**
    - **Salary progression**
      - Starts at the starting wage: `salary = ${starting_wage:,.0f}`
      - Increases by the COLA:  `salary = salary × {(cola_increase):.2f}`
      - Increases by the Step Raise [Years 2-5 only]: `salary = salary × {(step_increase):.2f}`
      - Increases by the Promotion Raise [Promotional years only]: `salary = salary × {(promotion_increase):.2f}`
    - **Pension contribution**
        - The pension tax is: `contribution = salary ×  {pension_tax_rate:.1f}`
        - Pay the pension tax: `total_pension_tax_paid += contribution`
    - **Hypothetical personal fund value**:
        - Increases with projected market returns: `personal_fund = personal_fund × {(index_returns_rate):.2f}`
        - Deposit the equivalent of the pension contribution: `personal_fund += contribution`

    **Retirement Years**
    - **Pension disbursements**
        - Pension allowance starts at the starting allowance: `allowance = ${starting_allowance:,.0f}`
        - Increases by by the COLA increase each year: `allowance = allowance × {(cola_increase):.2f}`
        - Redeem the pension allowance: `total_pension_redeemed += allowance`
    - **Hypothetical personal fund disbursements**
      - Withdraw the equivalent of the pension allowance: `personal_fund = personal_fund - allowance`
      - The remainder of the fund increases with the projected market returns: `personal_fund = personal_fund × {index_returns_rate}`

    The sequence of steps above calculates the values computed in the Summary section.
    """)


# Case Studies
st.divider()
st.header("Case Studies")

with st.expander("Case Study A"):
    st.markdown("""
        Alice's starting annual wage is 120,000. She assumes a standard step increase of 5.50%, COLA of 3%, promotion increase of 10%, pension tax rate of 10%, and index returns rate of 7%. She receives a promotion in years 10 and 20. She works 30 years and lives for 30 years in retirement. Her annual pension allowance totals 70,458.24.

        According to the calculator, at the end of Alice's 30 years of working, she will have paid about 785k in pension tax. If instead she had deposited the same amount as her pension tax into a tax-advantaged personal retirement fund option, she would have amassed a little over 2M in savings and investments. In her 30 years of retirement, she will have redeemed a bit over 3.35M in pension allowance. This amount is substantially greater than the 785k that she paid in pension tax, and greater than the 2M she would have amassed through the personal fund option at the time of retirement.

        The notable difference between the two options is that at the end of her life, with the personal retirement fund option, she ends up a lump sum worth over 5.5M to keep or give to whomstever she wishes, whereas with the pension option, she ends up with at most only the survivor beneift disbursements that she elected at the time of her departure from DWP (Options A-E; see RIS website for the specific details regarding the different Options.)

        My recommendation is that if your situation and assumptions are similar to Alice's, then saving for retirement on your own terms is of better value than the pension program.
    """)