# Pension vs. Personal Retirement Account Calculator

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pensioncalc.streamlit.app/)

## Overview

This Streamlit app compares the long-term financial outcomes of a **traditional pension (Option A)** against a **personal investment account (Option B)**. Enter your salary, career assumptions, and pension details, and the app runs both scenarios side by side using the same annual dollar amounts.

## Features

- **Result banner** that declares which option comes out ahead under your inputs, with explanation
- **Interactive line chart** showing Option B's fund balance over your full career and retirement, with shaded working/retirement phases and an optional reference line for annual pension withdrawals
- **Summary metrics**: total pension contributed, total pension received, fund value at retirement, final fund balance, break-even investment return rate, and years the personal fund covers
- **Break-even rate**: the minimum annual investment return at which Option B survives your full retirement — compared directly to your assumed rate
- **Year-over-year breakdown tables** for both working and retirement phases, showing contributions, withdrawals, and running balances
- **Pension allowance estimator**: enter your details and the app estimates your first-year allowance using the Final Average Salary (highest 36 consecutive months) × years of service × 2%
- **Configurable assumptions**: starting salary, COLA, step increases, promotions, pension contribution rate, index return rate, and retirement length

## How It Works

The calculator models two parallel scenarios using the same annual dollar amounts:

1. **Option A (pension)**: A fixed percentage of your salary is deducted each year. In retirement, you receive an annual allowance (from the estimator or entered manually) that grows with COLA each year.
2. **Option B (personal fund)**: The same annual deduction is invested in an index fund. The balance grows at your assumed annual return rate. In retirement, you withdraw the same dollar amount as the pension pays each year, and the remaining balance continues to grow.

The index return rate is nominal (not inflation-adjusted), consistent with how salaries and pension payments are modeled in nominal dollars. A reasonable default for a broad stock index is around 10%; for a more conservative balanced portfolio, 6–8%.

Annual contributions and withdrawals are assumed to occur at the end of each year.

## How to Use

Visit **[pensioncalc.streamlit.app](https://pensioncalc.streamlit.app)** or run locally:

```bash
pip install -r requirements.txt
streamlit run pension_calculator.py
```

## Assumptions and Limitations

- Salary grows annually by COLA. Step increases apply in configurable years. Promotions apply at specified years with a one-time salary bump.
- Investment returns are assumed constant each year — no market volatility or sequence-of-returns risk.
- Does not model vesting cliffs, employer match, mortality risk pooling, spousal/survivor benefits, disability protections, behavioral investing patterns, or tax implications.
- The pension allowance estimator targets Tier 2 / PEPRA-style formulas (2% × years × FAS). Other pension formulas require manual input.

This tool is for educational and exploratory use only. It is not a comprehensive actuarial model and should not substitute for professional financial advice.

## Disclaimer

This calculator does not constitute financial advice. Consult a licensed financial advisor or retirement specialist before making any pension or investment decisions.

## Comments, Suggestions, Questions

Please open an issue or contact me.
