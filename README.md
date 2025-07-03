# Pension vs. 403b Calculator

## Overview
Retirement planning is inherently complex, and the value of a pension depends on many variables. This tool is designed to illuminate those variables and support more informed, fact-based conversations among public workers, policymakers, and the broader public.

This Streamlit application is an interactive financial modeling tool designed to compare the long-term outcomes of participating in a traditional pension plan versus investing equivalent contributions into a personal retirement account, such as a 403(b). The model simulates a user-defined number of working years followed by a user-defined number of retirement years, allowing users to adjust key economic and personal assumptions to evaluate the projected financial impact of each strategy.

## Features
This app provides:
- A summary of total pension tax contributions, total pension benefits received, and the final value of personal retirement savings
- A line chart comparing the cumulative pension benefits and personal fund value over time
- A narrative conclusion to help interpret the results

## How to Use

Install the required Python packages:
```
pip install streamlit matplotlib
```

Then run:
```
streamlit run pension_vs_403b_calculator.py
```

## Limitations and Assumptions
- The model assumes fixed market and salary adjustment rates.
- Pension benefits are modeled as a flat annual payout with no compounding or survivor benefits. Your pension plan may have survivor benefits depending on your election at the time of retirement.
- The personal retirement fund is assumed to grow at a constant rate and is reduced by annual withdrawals during retirement.
- The model does not account for inflation-adjusted purchasing power, early retirement penalties, or changes in tax policy.

## Disclaimer
This tool is intended for educational and planning purposes only. It does not constitute financial advice. Users should consult a licensed financial advisor or retirement specialist before making any investment or pension-related decisions.

## Comments, suggestions, questions
Please open an issue or contact me.
