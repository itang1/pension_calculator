# Pension vs. Personal Retirement Account Calculator

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pensioncalc.streamlit.app/)

## Overview

This Streamlit app compares the long-term financial outcomes of a **traditional pension (Option A)** against a **personal investment account (Option B)**. Enter your salary, career assumptions, and pension details, and the app runs both scenarios side by side using the same annual dollar amounts.

The app has two pages that share the same expandable input panel and link to each other:

- **Steady Yearly Return** (default): assumes the same return before inflation every year and shows whether the account can cover all pension payments.
- **What If the Market Has Bad Years?** (`/market-swings`): replays the same scenario through 1,000 simulated market histories (Monte Carlo) and answers how often your own account runs out of money.

## Features

- **Result banner** describing whether the account covers all modeled payments, with an explanation of returns before and after inflation
- **Interactive line chart** showing Option B's fund balance over your full career and retirement, with an optional yearly pension-payment line and wrapping explanations that fit phones. Empty accounts stay at zero; unpaid income is shown separately
- **Monte Carlo page**: runs 1,000 randomized return sequences and shades the chart with the range of possible outcomes, so you can see how year-to-year market volatility could change the result, plus a descriptive result, an ending-balance histogram, and a depletion-timing chart
- **Summary metrics**: total pension contributed, total pension received, fund value at retirement, final fund balance, break-even investment return rate, and years your own account covers
- **Break-even rate**: the minimum annual investment return at which Option B survives your full retirement, compared directly to your assumed rate
- **Year-over-year breakdown tables** for both working and retirement phases, showing contributions, withdrawals, market returns, and running balances
- **Pension allowance estimator**: built-in plan rules pick the benefit factor from your age and years of service, apply the early-retirement reduction table, the 80% cap, vesting, and deferred pensions, and grow the pension in retirement by inflation up to a 2% COLA cap
- **Configurable assumptions**: starting salary, salary COLA, step increases (size and number of steps), promotion years, pension contribution rate, expected inflation, index return rate, retirement age, and the age to plan through
- **Inflation explained**: charts and summaries default to today's buying power. Investment returns are entered before inflation. A manual pension amount can be monthly or yearly and is converted, when needed, using inflation through the first payment year
- **Ages on every chart**, a **today's-dollars toggle**, a **return-rate chart** showing how the answer changes with the return, and **shareable links** created on request with the active inputs
- **Case studies** showing different funding outcomes, with one-click loading and an option to restore your previous inputs
- **Feedback form** to submit questions and comments

## How to Use

The app is hosted at **[pensioncalc.streamlit.app](https://pensioncalc.streamlit.app)**.

> **Source-available, not open-source.** This repository is published for viewing only. Per the [LICENSE](LICENSE), no permission is granted to copy, modify, redistribute, or run this code without the author's written permission.

## Disclaimer

This calculator does not constitute financial advice. It operates on limitations and assumptions. Consult a licensed financial advisor or retirement specialist before making any pension or investment decisions.

## Comments, Suggestions, Questions

Please use the in-app feedback form, open an issue, or contact me.
