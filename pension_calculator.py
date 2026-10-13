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
# page body (not the always-rendered sidebar), or only show in one allowance
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
if "_example_label" in st.session_state:
    st.info("An example scenario is loaded. You can return to the inputs you entered before trying examples.")
    st.button("Restore my previous inputs", key="restore_inputs", on_click=common.restore_previous_inputs)

show_real = st.toggle(
    "Show amounts in today's dollars",
    value=True,
    key="in_real",
    help=(
        f"Charts and summaries: buying power at today's ({common.CURRENT_YEAR}) prices. "
        "A displayed \\$1,000 means it could buy what \\$1,000 buys today. "
        "Yearly tables and case studies show amounts paid in each year, as labeled. "
        "Turn this off to see every amount as paid in each year instead."
    ),
)
# Sidebar inputs render on every page, so their widget state persists across
# page switches without any pinning. Views read inputs/results from
# session_state rather than importing from here (which would re-run the script).
inputs = common.render_sidebar()
if inputs["problems"]:
    # Stop only after the whole sidebar has rendered, so no input is forgotten.
    st.error("Fix the input marked in red in the sidebar to see your results.")
    st.stop()
st.session_state["_inputs"] = inputs
_nominal = common.compute_results(inputs)
st.session_state["_results_nominal"] = _nominal
st.session_state["_results"] = common.deflate_results(_nominal, inputs) if show_real else _nominal
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
common.count_pageview(pg)
if "session_tracked" not in st.session_state:
    st.session_state.session_tracked = True
    common.log_visit()
