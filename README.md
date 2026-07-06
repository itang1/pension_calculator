# Pension vs. Personal Retirement Account Calculator

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pensioncalc.streamlit.app/)

## Overview

This Streamlit app compares the long-term financial outcomes of a **traditional pension (Option A)** against a **personal investment account (Option B)**. Enter your salary, career assumptions, and pension details, and the app runs both scenarios side by side using the same annual dollar amounts.

The app is written for readers with no personal-finance background: each page answers one plain question, verdicts come before charts, and risk is phrased as natural frequencies ("18 out of every 100 futures") rather than probabilities.

## The two pages

- **The Comparison** (default): assumes the market returns one flat rate every year and answers "which option wins, and by how much?" — verdict banner first, then an annotated chart, summary metrics, and year-over-year breakdown tables.
- **What If the Market Has Bad Years?** (`/market-swings`): replays the same scenario through 1,000 simulated market histories (Monte Carlo) and answers "how often does the personal fund run out of money?" — with a risk-tiered verdict, the range of outcomes on the chart, an ending-balance distribution, and a depletion-timing chart.

Both pages share the same sidebar inputs, and each links to the other; a "reality check" callout on the comparison page carries the headline risk number so it is never hidden behind a click.

## Features

- **Result banner** that declares which option comes out ahead under your inputs, in plain language, above the chart it summarizes
- **Interactive line chart** showing Option B's fund balance over your full career and retirement, annotated with the verdict at the point where it happens (money left over, or the year the fund runs dry)
- **Market-risk page**: 1,000 randomized return sequences with a traffic-light verdict, outcome bands, ending-balance histogram, and depletion-timing histogram
- **Summary metrics**: total pension contributed, total pension received, fund value at retirement, final fund balance, break-even investment return rate, and years the personal fund covers
- **Break-even rate**: the minimum annual investment return at which Option B survives your full retirement, compared directly to your assumed rate
- **Year-over-year breakdown tables** for both working and retirement phases, showing contributions, withdrawals, market returns, and running balances
- **Pension allowance estimator**: enter your career details and the app estimates your first-year allowance using a formula of my choice
- **Configurable assumptions**: starting salary, COLA, step increases, promotion years, pension contribution rate, index return rate, retirement age, and retirement length
- **One-click case studies**: a scenario where each option wins, loadable into the calculator with a single button
- **Feedback form** on both pages, recording which page it was submitted from

## How to Use

The app is hosted at **[pensioncalc.streamlit.app](https://pensioncalc.streamlit.app)**.

> **Source-available, not open-source.** This repository is published for viewing only. Per the [LICENSE](LICENSE), no permission is granted to copy, modify, redistribute, or run this code without the author's written permission.

## Disclaimer

This calculator does not constitute financial advice. It operates on limitations and assumptions. Consult a licensed financial advisor or retirement specialist before making any pension or investment decisions.

## Comments, Suggestions, Questions

Please use the in-app feedback form, open an issue, or contact me.
