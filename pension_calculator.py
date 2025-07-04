import streamlit as st
# import matplotlib.pyplot as plt


st.title("Pension vs. 403b Savings Calculator")


with st.expander("What is a pension?"):
    st.markdown("""
    **[From Wikipedia:](https://en.wikipedia.org/wiki/Pension)** A pension is a fund into which amounts are paid regularly during an individual's working career, and from which periodic payments are made to support the person's retirement from work. A pension may be either a "defined benefit plan", where defined periodic payments are made in retirement and the sponsor of the scheme (e.g. the employer) must make further payments into the fund if necessary to support these defined retirement payments, or a "defined contribution plan", under which defined amounts are paid in during working life, and the retirement payments are whatever can be afforded from the fund. 
    """)
    
with st.expander("Purpose of this calculator"):
    st.markdown("""
Many civil service employees (e.g. teachers, government workers) mandatorily participate in a defined-benefit pension plan. These workers are required to contribute a portion of their salary to a pension system, and, in return, are promised a fixed income in retirement. In contrast, the private sector has largely shifted to defined-contribution plans like 401(k)s and 403(b)s, where employees voluntarily contribute a percentage of their income and bear the responsibility for managing their own retirement savings.\n
This structural difference has fueled public debate and, in some cases, resentment. Critics argue that public pensions are outdated, fiscally unsustainable, and [overly generous](https://www.forbes.com/sites/waynewinegarden/2018/09/20/the-opportunity-created-by-californias-overly-generous-public-pensions/) when compared to the more uncertain and self-funded retirement options available to most private-sector workers. Discussion forum narratives often portray public pensions as a burden on taxpayers or as evidence of government inefficiency. In several states, unfunded pension liabilities have become [central issues](https://www.pew.org/en/research-and-analysis/articles/2022/07/07/states-unfunded-pension-liabilities-persist-as-major-long-term-challenge) in budget negotiations and political campaigns.\n
At the same time, many public employees feel caught in a system they did not choose. Participation in the pension plan is mandatory, and workers typically have little control over how their contributions are invested. In many cases, they are also excluded from Social Security. Some view the pension as a perk, but others would prefer the flexibility and autonomy of managing their own retirement savings in a tax-deferred account, but are not given that option.\n
I created this calculator to bring clarity to the ongoing debate about the fairness, sustainability, and value of public pension systems—specifically whether these mandatory plans provide better retirement outcomes than if employees instead invested equivalent contributions in personal, tax-deferred accounts such as 403(b) or 457(b) plans.\n
This calculator allows users to compare the long-term value of a traditional pension with a hypothetical scenario in which the same contributions are invested in a personal, tax-deferred retirement account such as a 457(b) deferred compensation plan. By adjusting assumptions like salary growth, investment returns, and retirement duration, users can explore whether the pension system offers a better outcome for their specific circumstances, or whether self-directed savings might be more advantageous.\n
Retirement planning is inherently complex, and the value of a pension depends on many variables. This tool is designed to illuminate those variables and support more informed, fact-based conversations among public workers, policymakers, and the broader public. 
    """)

# Input form
with st.form("retirement_form"):
    st.header("Market Assumptions")
    col1, col2, col3 = st.columns(3)
    with col1:
        step_increase = st.number_input(
            "Step Increase (%)",
            value=5.5,
            help="Annual raise from step progression (e.g., moving up a salary scale)."
        ) / 100 + 1
        pension_tax_rate = st.number_input(
            "Pension Tax Rate (%)",
            value=10.0,
            help="Percentage of your salary contributed to the pension system each year."
        ) / 100
    with col2:
        inflation_increase = st.number_input(
            "Cost of Living Adjustment (COLA) (%)",
            value=3.0,
            help="Annual salary adjustment announced each October, typically between 2–5%."
        ) / 100 + 1
    with col3:
        promotion_increase = st.number_input(
            "Promotion Increase (%)",
            value=10.0,
            help="Salary bump when you receive a promotion."
        ) / 100 + 1
        index_returns_rate = st.number_input(
            "Index Returns Rate (%)",
            value=7.0,
            help="Annual return rate of your personal retirement investments (e.g., 403b)."
        ) / 100 + 1

    st.header("Personal Assumptions")
    col4, col5, col6 = st.columns(3)
    with col4:
        starting_wage = st.number_input(
            "Starting Annual Wage ($)",
            value=120000,
            help="Your initial yearly salary before any raises or promotions."
        )
        work_years = st.number_input(
            "Years to Work",
            value=30,
            min_value=1,
            max_value=60,
            step=1,
            help="Number of years you plan to work before retirement."
        )
    with col5:
        retirement_years = st.number_input(
            "Years After Retirement",
            value=30,
            min_value=1,
            max_value=60,
            step=1,
            help="How many years you expect to live after retiring."
        )
    with col6:
        retirement_allowance = st.number_input(
            "Annual Pension Allowance ($)",
            value=12 * 5871.52,
            help="Estimate your annual pension payout. You can calculate yours using the RIS website pension calculator."
        )

    st.markdown(
        "<small>You can estimate your pension using the <a href='https://wp03vm13risp1:8443/WPERP/' target='_blank'>RIS website pension calculator</a>.</small>",
        unsafe_allow_html=True
    )

    promotion_years_input = st.text_input(
        "Promotion Years (comma-separated)",
        "10,20",
        help="Years in which you expect to be promoted (e.g., 10, 20). Should fall within your working years."
    )

    submitted = st.form_submit_button("Run Simulation")


# Results
st.divider()
st.subheader("Simulation Results")

if not submitted:
    st.write("Click the **Run Simulation** button above to generate the plot.")

if submitted:
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

    # Tracking for visualization
    years = []
    pension_fund_values = []
    personal_fund_values = []

    # Work phase
    for work_year in range(1, int(work_years) + 1):
        pension_tax_paid += current_wage * pension_tax_rate
        personal_retirement_fund = (personal_retirement_fund * index_returns_rate) + current_wage * pension_tax_rate

        years.append(f"W{work_year}")
        pension_fund_values.append(0)
        personal_fund_values.append(personal_retirement_fund)

        current_wage *= inflation_increase
        if 2 <= work_year <= 5:
            current_wage *= step_increase
        if work_year in promotion_years:
            current_wage *= promotion_increase

    # Retirement phase
    for ret_year in range(1, retirement_years + 1):
        pension_redeemed += retirement_allowance
        personal_retirement_fund = (personal_retirement_fund - retirement_allowance) * index_returns_rate

        years.append(f"R{ret_year}")
        pension_fund_values.append(pension_redeemed)
        personal_fund_values.append(personal_retirement_fund)

    # Results
    st.subheader("Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Pension Tax Paid", f"${pension_tax_paid:,.0f}")
    col2.metric("Total Pension Redeemed", f"${pension_redeemed:,.0f}")
    col3.metric("Final Personal Fund Value", f"${personal_retirement_fund:,.0f}")

    # Plot
    st.subheader("Fund Growth Over Time")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(years, pension_fund_values, label="Pension Redeemed", color="blue")
    ax.plot(years, personal_fund_values, label="Personal Retirement Fund", color="green")
    ax.set_xlabel("Year")
    ax.set_ylabel("Amount ($)")
    ax.set_title("Retirement Fund Comparison")
    ax.legend()

    # Show only every 5th year label to reduce clutter
    tick_interval = 5
    visible_ticks = [i for i in range(len(years)) if i == 0 or (i + 1) % tick_interval == 0]
    ax.set_xticks(visible_ticks)
    ax.set_xticklabels([years[i] for i in visible_ticks], rotation=45)

    st.pyplot(fig)


# Conclusion
st.markdown("""
---
### Conclusion

This calculator compares the value of a traditional pension with a personal retirement savings strategy under your assumptions.

- If your personal fund ends with a large balance, it may offer more flexibility and inheritance potential.
- If your pension provides more consistent income, it may offer peace of mind and stability.

Always consult a financial advisor before making major retirement decisions.
""")
