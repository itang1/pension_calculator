# Pension vs. Personal Retirement Account Calculator

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pensioncalc.streamlit.app/)

## Overview

This interactive Streamlit app compares the long-term financial outcomes of a **traditional pension** against a **self-managed personal retirement account** (e.g., 457(b), 403(b), or 401(k)). It lets you adjust assumptions like salary growth, investment returns, and retirement length to see which option might come out ahead under your specific circumstances.

The goal is to support evidence-based, data-driven comparisons so that individuals — particularly public sector employees who are often required to participate in pension systems — can form informed opinions rather than rely on emotional arguments or general rules of thumb.

## Features

- **Side-by-side comparison** of total pension contributions, total pension benefits received, and personal fund value at retirement and end of retirement
- **Interactive line chart** showing cumulative pension income and personal fund balance over time
- **Year-over-year breakdown tables** for both working and retirement phases
- **Configurable assumptions**: starting salary, step increases, COLA, promotions, pension contribution rate, index returns rate, and retirement length
- **Case study** with a concrete worked example using default values

## How It Works

The calculator models two parallel scenarios using the same annual contribution amount:

1. **Pension**: You contribute a fixed percentage of your salary each year. In retirement, you receive an annual allowance (entered as a fixed starting value) that grows with COLA each year.
2. **Personal fund**: You invest the same annual amount into an index fund. The balance grows at a configurable annual return rate. In retirement, you withdraw the same amount as the pension allowance each year, and the remaining balance continues to grow (or shrink).

Deposits and withdrawals are assumed to occur at the end of each year and do not affect that year's market returns.

## How to Use

Visit **[pensioncalc.streamlit.app](https://pensioncalc.streamlit.app)** or run locally:

```bash
pip install -r requirements.txt
streamlit run pension_calculator.py
```

## Assumptions and Limitations

- Salary grows annually by COLA. Step increases apply in years 2–5. Promotions can be configured at arbitrary years.
- The personal fund assumes consistent annual contributions during working years and consistent withdrawals during retirement — no simulation of market volatility.
- Does not model mortality risk pooling, spousal/survivor benefits, disability protections, behavioral investing patterns, or tax implications.
- The starting pension allowance must be entered manually (e.g., from your pension system's online estimator).

This tool is intended for educational and exploratory use only. It is not a comprehensive actuarial model and should not substitute for professional financial advice.

## Disclaimer

This calculator does not constitute financial advice. Users should consult a licensed financial advisor or retirement specialist before making any investment or pension-related decisions.

## Comments, Suggestions, Questions

Please open an issue or contact me.
