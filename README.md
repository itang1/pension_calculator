# Pension vs. Personal Retirement Account Calculator

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pensioncalc.streamlit.app/)

## Overview

This Streamlit app compares the long-term financial outcomes of a **traditional pension (Option A)** against a **personal investment account (Option B)**. Enter your salary, career assumptions, and pension details, and the app runs both scenarios side by side using the same annual dollar amounts.

The app has two pages that share the same sidebar inputs and link to each other:

- **Base Comparison: Flat Rate** (default): assumes the market returns one flat rate every year and answers which option wins, and by how much.
- **What If the Market Has Bad Years?** (`/market-swings`): replays the same scenario through 1,000 simulated market histories (Monte Carlo) and answers how often the personal fund runs out of money.

## Features

- **Result banner** that declares which option comes out ahead under your inputs, with explanation
- **Interactive line chart** showing Option B's fund balance over your full career and retirement, with labeled working/retirement phases, an optional reference line for annual pension withdrawals, and the verdict annotated at the point where it happens (money left over, or the year the fund runs dry)
- **Monte Carlo page**: runs 1,000 randomized return sequences and shades the chart with the range of possible outcomes, so you can see how year-to-year market volatility could change the result, plus a risk-tiered verdict, an ending-balance histogram, and a depletion-timing chart
- **Summary metrics**: total pension contributed, total pension received, fund value at retirement, final fund balance, break-even investment return rate, and years the personal fund covers
- **Break-even rate**: the minimum annual investment return at which Option B survives your full retirement, compared directly to your assumed rate
- **Year-over-year breakdown tables** for both working and retirement phases, showing contributions, withdrawals, market returns, and running balances
- **Pension allowance estimator**: enter your career details and the app estimates your first-year allowance using a formula of my choice
- **Configurable assumptions**: starting salary, COLA, step increases, promotion years, pension contribution rate, index return rate, retirement age, and retirement length
- **Case studies** showing scenario where each option wins, with full settings to reproduce in the calculator with one click
- **Feedback form** to submit questions and comments

## How to Use

The app is hosted at **[pensioncalc.streamlit.app](https://pensioncalc.streamlit.app)**.

> **Source-available, not open-source.** This repository is published for viewing only. Per the [LICENSE](LICENSE), no permission is granted to copy, modify, redistribute, or run this code without the author's written permission.

## Disclaimer

This calculator does not constitute financial advice. It operates on limitations and assumptions. Consult a licensed financial advisor or retirement specialist before making any pension or investment decisions.

## Comments, Suggestions, Questions

Please use the in-app feedback form, open an issue, or contact me.
