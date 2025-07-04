# Pension vs. 403b Calculator

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pensioncalc.streamlit.app/)

## Overview
This Streamlit application is an interactive financial modeling tool designed to allow uers to model variables such as salary growth, expected investment returns, and number of years spent in retirement. It offers a data-driven comparison between the long-term value of a pension vs. a hypothetical self-managed investment strategy. The goal of this calculator is to support evidence-based dialogue so that individuals can form fact-based opinions and make informed decisions rather than rely on emotional arguments or misinformation.

## Features
This app provides:
- A summary of total pension tax contributions, total pension benefits received, and the final value of personal retirement savings
- A line chart comparing the cumulative pension benefits and personal fund value over time
- A narrative conclusion to help interpret the results

## How to Use

Install the required Python packages:
```
$ pip install -r requirements.txt
```

Then run:
```
$ streamlit run pension_calculator.py
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
