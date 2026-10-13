"""Entry point: shared chrome (title, inputs, analytics) + page routing.

This file stays the Streamlit main script so the existing deployment config
keeps working. Everything rendered here appears on every page; page-specific
content lives in view_comparison.py and view_market_swings.py.
"""

from pathlib import Path

import streamlit as st

import common
import view_comparison
import view_market_swings

st.set_page_config(
    page_title="Pension Calculator",
    layout="wide",
    page_icon=str(Path(__file__).parent / "assets" / "icon.png"),
)

# st.page_link renders its label on one non-wrapping line and truncates what
# doesn't fit. The banner pointer under the result banner is a full sentence,
# so let page-link labels wrap.
common.render_html(
    """<style>
    [data-testid="stPageLink"] a,
    [data-testid="stPageLink"] p {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        height: auto !important;
    }
    </style>"""
)

# Keep conditionally rendered widget state alive. Streamlit drops the state of
# any widget that is not rendered during a rerun, so widgets that live in a
# page body (not the always-rendered input panel), or only show in one allowance
# mode, need this re-assignment pin.
for _k in ("mc_std", "allowance_manual", "in_allowance_basis", "in_allowance_period",
           "in_wage", "in_wage_mode", "in_current_wage"):
    if _k in st.session_state:
        st.session_state[_k] = st.session_state[_k]

# Inputs from a shared link load before any widget (including the toggle
# below) is created, since widget state can only be seeded beforehand.
common.apply_query_params()
common.apply_pending_preset()

st.title("Is Your Pension Worth It?")
input_panel = st.expander("Start here: enter your details", key="input_panel", on_change="rerun")
st.caption(
    "This calculator uses one set of pension rules for members hired in 2014 or later. "
    "Check that these rules match your pension before using the estimate."
)
with st.expander("Check the pension rules used here"):
    st.markdown("""
- Members contribute **10% of pay**. Final average salary uses the **highest 3 consecutive years**.
- With at least 5 years of service, the annual factor is **1.5% at age 60** or **2% at age 63**.
- With at least 30 years of service, the factor is **2%**, rising to **2.1% at age 63**. Payments are unreduced from age 55. Earlier payments are reduced using an age-based table.
- The benefit is capped at **80% of final average salary**.
- Leaving before age 60 with 5 to 29 years of service means payments start at **60**, using the **1.5%** factor, with **no yearly increases**.
- With fewer than 5 years, there is **no lifetime pension**. Contributions are refunded with **6.5% annual interest**.
- For eligible pensions, yearly increases follow inflation, capped at **2%**. Salary raises are separate.

These rules do not cover every public pension. Entering a manual amount changes only the payment amount, not these eligibility or increase rules.
""")
if "_example_label" in st.session_state:
    st.info("An example scenario is loaded. You can return to the inputs you entered before trying examples.")
    st.button("Restore my previous inputs", key="restore_inputs", on_click=common.restore_previous_inputs)

show_real = st.toggle(
    f"Show amounts in {common.CURRENT_YEAR} dollars",
    value=True,
    key="in_real",
    help=(
        f"Prices rise over time, so a dollar in 2060 will buy much less than a dollar in "
        f"{common.CURRENT_YEAR}. Turn this on to see every amount as what it would buy in "
        f"{common.CURRENT_YEAR}, using the inflation rate in the input panel. Return rates stay as entered."
    ),
)
if show_real:
    st.caption(
        f"Charts and summary amounts show what the money could buy in {common.CURRENT_YEAR}. "
        "The yearly tables and case studies use dollars from each year and are labeled separately."
    )
else:
    st.caption("Amounts are shown in the dollars of the year they occur. Future amounts can look large because prices rise. Turn on today's dollars to compare buying power.")

# Shared inputs render on every page, so their widget state persists across
# page switches without any pinning. Views read inputs/results from
# session_state rather than importing from here (which would re-run the script).
with input_panel:
    inputs = common.render_inputs()
if inputs["problems"]:
    # Stop only after all inputs render, so no input is forgotten.
    st.error("Open 'Start here: enter your details' and fix the input marked in red to see your results.")
    st.stop()
st.session_state["_inputs"] = inputs
_nominal = common.compute_results(inputs)
st.session_state["_results_nominal"] = _nominal
st.session_state["_results"] = common.deflate_results(_nominal, inputs) if show_real else _nominal
with input_panel:
    common.render_share_section(inputs)

_comparison_page = st.Page(
    view_comparison.render,
    title="Steady Yearly Return",
    icon="⚖️",
    url_path="comparison",
    default=True,
)
_market_page = st.Page(
    view_market_swings.render,
    title="What If the Market Has Bad Years?",
    icon="🎢",
    url_path="market-swings",
)

# Views link to each other through these page objects (st.page_link needs the
# StreamlitPage instance for function-based pages).
st.session_state["_pages"] = {"comparison": _comparison_page, "market": _market_page}

pg = st.navigation([_comparison_page, _market_page], position="top")
pg.run()

# Analytics run after the page has rendered, so the visit logging (a
# geolocation lookup plus a Sheets write) never delays the first paint.
common.render_privacy_notice()
common.count_pageview(pg)
if "session_tracked" not in st.session_state:
    st.session_state.session_tracked = True
    common.log_visit()
