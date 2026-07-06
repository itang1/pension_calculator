"""Entry point: shared chrome (title, sidebar inputs, analytics) + page routing.

This file stays the Streamlit main script so the existing deployment config
keeps working. Everything rendered here appears on every page; page-specific
content lives in view_comparison.py and view_market_swings.py.
"""

import streamlit as st
import streamlit.components.v1 as components

import common
import view_comparison
import view_market_swings

st.set_page_config(layout="wide")

# Keep page-local widget state alive across page switches. Streamlit drops the
# state of any widget that is not rendered during a rerun, so widgets that live
# in a page body (not the always-rendered sidebar) need this re-assignment pin.
for _k in ("mc_std",):
    if _k in st.session_state:
        st.session_state[_k] = st.session_state[_k]

if "session_tracked" not in st.session_state:
    st.session_state.session_tracked = True
    components.html("""
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-7SKCXXZV9W"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', 'G-7SKCXXZV9W');
        </script>
    """, height=0)
    common.log_visit()

st.title("Is Your Pension Worth It?")

# Sidebar inputs render on every page, so their widget state persists across
# page switches without any pinning. Views read inputs/results from
# session_state rather than importing from here (which would re-run the script).
common.apply_pending_preset()
inputs = common.render_sidebar()
st.session_state["_inputs"] = inputs
st.session_state["_results"] = common.compute_results(inputs)

_comparison_page = st.Page(
    view_comparison.render,
    title="The Comparison",
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

pg = st.navigation([_comparison_page, _market_page])
pg.run()
