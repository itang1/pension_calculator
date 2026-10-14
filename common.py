"""Shared infrastructure for the multipage app.

Holds everything both pages need: Google Sheets plumbing, client metadata,
the shared inputs, cached simulation wrappers, the fund chart builder, and
the feedback form. Page-specific copy and layout live in the view modules.

Per-user data is passed between the entry script and the views via
``st.session_state`` (keys ``_inputs``, ``_results`` for display, and
``_results_nominal`` in future dollars), never via module
globals, which are process-wide and would leak between sessions.
"""

import ipaddress
import json
import logging
import collections
import math
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

import gspread
import numpy as np
import pandas as pd
import streamlit as st
from plotly import graph_objects as go
from user_agents import parse as _parse_ua

import simulation

_logger = logging.getLogger(__name__)

# "Today" for dollar labels and the hire-year input. Everything that says
# "today's dollars" means dollars of this calendar year.
CURRENT_YEAR = date.today().year

_SPREADSHEET_ID = "1-H0MxbLs4QhES0tbXT4EztNm-5y-GY_jOzwJnwprP1M"

# Abuse controls for the feedback write path (see [H-3]).
_FEEDBACK_MAX_CHARS = 2000
_FEEDBACK_COOLDOWN_SECONDS = 30

_FEEDBACK_HEADERS = [
    "Timestamp", "Feedback",
    "Starting Wage", "Work Years", "Retirement Years",
    "COLA %", "Index Returns %", "Pension Contribution %", "First-Year Allowance",
    "Pension Contributed", "Pension Received", "Personal Fund at Retirement",
    "Final Personal Fund Balance", "Break-even Rate %", "Years Personal Fund Covers", "Winner",
    "IP", "Country", "Region", "City", "Zip", "Lat", "Lon",
    "Timezone", "ISP", "VPN/Proxy", "Mobile Network",
    "Accept-Language", "Referrer", "Platform", "Mobile Browser",
    "Browser", "Browser Version", "OS", "OS Version", "Device",
    # Added with the two-page split: which page the feedback came from, and
    # the Monte Carlo settings/result the user was looking at.
    "Page", "MC Volatility %", "MC Depletion %",
]


@st.cache_resource
def _get_spreadsheet():
    return gspread.service_account_from_dict(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    ).open_by_key(_SPREADSHEET_ID)


def _ensure_headers(ws, headers):
    """Insert or extend the header row once if needed.

    Called only from the cached worksheet getters, so it runs at most once per
    server process instead of on every write. This keeps the check-then-act
    race to a single startup call. When new columns are appended to a headers
    list (e.g. the page-context columns), the existing sheet's header row is
    extended in place so old and new rows stay aligned.
    """
    first_row = ws.row_values(1)
    if not first_row or first_row[0] != headers[0]:
        ws.insert_row(headers, 1)
    elif len(first_row) < len(headers):
        ws.update(values=[headers], range_name="A1")


@st.cache_resource
def _get_feedback_sheet():
    ws = _get_spreadsheet().sheet1
    _ensure_headers(ws, _FEEDBACK_HEADERS)
    return ws


_GEO_FIELDS = "status,country,regionName,city,zip,lat,lon,timezone,isp,proxy,mobile"


def _geo_lookup_url(ip: str):
    """Return a safe, encrypted geolocation URL for ``ip`` or ``None``.

    Addresses two audit findings:

    * [H-1] The IP originates from a client-controlled ``X-Forwarded-For``
      header. We parse it with :func:`ipaddress.ip_address` and discard
      anything that is not a real address, so no attacker-supplied text can
      ever be interpolated into the outbound URL.
    * [C-2] The free ip-api.com endpoint is plaintext HTTP and its terms
      restrict production use. We only ever call the paid HTTPS endpoint, and
      only when an API key is configured in ``st.secrets["ip_api_key"]``.
      Without a key we skip the lookup entirely rather than leak the visitor's
      IP over an unencrypted, terms-violating channel.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_unspecified:
        return None

    try:
        key = st.secrets["ip_api_key"]
    except Exception:
        key = None
    if not key:
        return None

    return (
        f"https://pro.ip-api.com/json/{addr}"
        f"?fields={_GEO_FIELDS}&key={urllib.parse.quote(str(key), safe='')}"
    )


def _client_metadata():
    ip = ua_str = lang = referrer = platform_hdr = mobile_hdr = "unknown"
    country = region = city = zip_code = timezone = isp = "unknown"
    lat = lon = is_vpn = is_mobile_net = "unknown"
    browser = browser_ver = os_name = os_ver = device = "unknown"

    try:
        hdrs = st.context.headers
        ip = hdrs.get("X-Forwarded-For") or hdrs.get("X-Real-Ip") or "unknown"
        ip = ip.split(",")[0].strip() or "unknown"
        ua_str = hdrs.get("User-Agent", "unknown")
        lang = hdrs.get("Accept-Language", "unknown")
        referrer = hdrs.get("Referer", "unknown")
        platform_hdr = hdrs.get("Sec-Ch-Ua-Platform", "unknown").strip('"')
        mobile_hdr = hdrs.get("Sec-Ch-Ua-Mobile", "unknown")
    except Exception:
        pass

    geo_url = _geo_lookup_url(ip)
    if geo_url is not None:
        try:
            with urllib.request.urlopen(geo_url, timeout=3) as r:
                geo = json.loads(r.read())
            if geo.get("status") == "success":
                country = geo.get("country", "unknown")
                region = geo.get("regionName", "unknown")
                city = geo.get("city", "unknown")
                zip_code = str(geo.get("zip", "unknown"))
                lat = geo.get("lat", "unknown")
                lon = geo.get("lon", "unknown")
                timezone = geo.get("timezone", "unknown")
                isp = geo.get("isp", "unknown")
                is_vpn = geo.get("proxy", "unknown")
                is_mobile_net = geo.get("mobile", "unknown")
        except Exception:
            # Geolocation is best-effort; log for observability but never fail
            # the request over it (previously a silent bare `except: pass`).
            _logger.debug("Geolocation lookup failed", exc_info=True)

    if ua_str != "unknown":
        try:
            ua = _parse_ua(ua_str)
            browser = ua.browser.family
            browser_ver = ua.browser.version_string
            os_name = ua.os.family
            os_ver = ua.os.version_string
            device = "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop" if ua.is_pc else "other"
        except Exception:
            pass

    return (
        ip, country, region, city, zip_code, lat, lon,
        timezone, isp, is_vpn, is_mobile_net,
        lang, referrer, platform_hdr, mobile_hdr,
        browser, browser_ver, os_name, os_ver, device,
    )


# Site-wide cap on Google Sheets writes. The per-session feedback cooldown
# does not stop many new sessions at once, so this process-wide limiter (an
# intentional module global, shared by every visitor) protects the sheet's
# write quota. Visits are simply not logged while the cap is reached.
_SHEET_WRITES_PER_MINUTE = 30
_sheet_write_times = collections.deque()
_sheet_write_lock = threading.Lock()


def _sheet_write_allowed():
    now = time.monotonic()
    with _sheet_write_lock:
        while _sheet_write_times and now - _sheet_write_times[0] > 60:
            _sheet_write_times.popleft()
        if len(_sheet_write_times) >= _SHEET_WRITES_PER_MINUTE:
            return False
        _sheet_write_times.append(now)
        return True


def _append_feedback(row: list):
    """Append a feedback row. Returns ``None`` on success, else ``True``.

    [H-2] The raw exception is logged server-side only. gspread errors can
    contain the spreadsheet ID, service-account email, and API payloads, so we
    never surface the exception text to end users.
    """
    if not _sheet_write_allowed():
        return True
    try:
        _get_feedback_sheet().append_row(row, value_input_option="RAW")
        return None
    except Exception:
        _logger.exception("Failed to append feedback row")
        return True


_VISIT_HEADERS = [
    "Timestamp",
    "IP", "Country", "Region", "City", "Zip", "Lat", "Lon",
    "Timezone", "ISP", "VPN/Proxy", "Mobile Network",
    "Accept-Language", "Referrer", "Platform", "Mobile Browser",
    "Browser", "Browser Version", "OS", "OS Version", "Device",
]


@st.cache_resource
def _get_visit_sheet():
    ss = _get_spreadsheet()
    try:
        ws = ss.worksheet("Visits")
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title="Visits", rows=5000, cols=len(_VISIT_HEADERS))
    _ensure_headers(ws, _VISIT_HEADERS)
    return ws


def log_visit():
    if not _sheet_write_allowed():
        return
    try:
        _get_visit_sheet().append_row(
            [datetime.now(timezone.utc).isoformat(timespec="seconds"), *_client_metadata()],
            value_input_option="RAW",
        )
    except Exception:
        pass


_GOATCOUNTER_URL = "https://itang1.goatcounter.com/count"


def count_pageview(page):
    """Count a page view in GoatCounter, once per page switch.

    Streamlit reruns the whole script on every widget change, so the view is
    only counted when the visitor lands on a different page. GoatCounter's
    count.js skips iframes and Streamlit pages have no editable <head>, so
    this uses GoatCounter's no-JavaScript image pixel. Paths are prefixed
    with the host, matching the other apps that share the dashboard.
    """
    path = "/" + (page.url_path or "")
    if st.session_state.get("_gc_last_path") == path:
        return
    st.session_state["_gc_last_path"] = path
    try:
        host = urllib.parse.urlsplit(st.context.url or "").netloc or st.context.headers.get("Host", "")
    except Exception:
        return
    hostname = host.split(":")[0]
    if not host or hostname in ("localhost", "127.0.0.1") or hostname.endswith(".local"):
        return
    # Every value is URL-encoded with no safe characters, so header text can
    # never break out of the src attribute.
    query = urllib.parse.urlencode({
        "p": host + path,
        "t": page.title,
        "rnd": f"{time.time_ns()}",
    }, quote_via=urllib.parse.quote, safe="")
    render_html(
        f'<img src="{_GOATCOUNTER_URL}?{query}" alt="" width="1" height="1" '
        f'style="position:absolute;opacity:0;pointer-events:none">'
    )


# The math lives in simulation.py with no Streamlit dependency,
# so it is unit-testable; caching is applied here at the app boundary.
run_simulation = st.cache_data(max_entries=512)(simulation.run_simulation)
compute_breakeven_rate = st.cache_data(max_entries=256)(simulation.compute_breakeven_rate)
run_monte_carlo = st.cache_data(max_entries=64)(simulation.run_monte_carlo)
compute_fas = simulation.compute_fas


def fmt_rate(pct):
    """Format a return rate (%) for copy; the break-even can be ``math.inf``."""
    if math.isinf(pct):
        return f"over {simulation.BREAKEVEN_CAP_PCT:.0f}%"
    return f"{pct:.1f}%"


def fmt_share(prob):
    """Format a share of futures (0-1) as a percent that never rounds a real risk to 0%."""
    pct = prob * 100
    if 0 < pct < 1:
        return f"{pct:.1f}%"
    return f"{pct:.0f}%"


def inputs_summary_html(inputs, res):
    """One line restating what the results assume, for the sidebar-hint boxes.

    Phone visitors start with the sidebar collapsed, so this tells them what
    the page is showing. HTML (not markdown), with "&#36;" for dollar signs so
    nothing is read as math.
    """
    if inputs["hire_year"] < CURRENT_YEAR and st.session_state.get("in_wage_mode") == "My wage today":
        wage = (f"&#36;{st.session_state['in_current_wage']:,.0f} wage today "
                f"(hired in {inputs['hire_year']})")
    else:
        wage = f"&#36;{inputs['starting_wage']:,.0f} starting wage in {inputs['hire_year']}"
    hire_age = inputs["retirement_age"] - inputs["work_years"]
    return (
        f"<strong>Your results below assume:</strong> {wage} · hired at {hire_age} · "
        f"retire at {inputs['retirement_age']} · {inputs['retirement_years']} years retired · "
        f"{res['index_return_pct']:.1f}% yearly investment growth.<br>"
        "<span style='font-size:0.9em'>On a phone, tap the » arrow at the top left to open the sidebar. "
        "To save or share your numbers, use <em>Share These Inputs</em> at the bottom of the sidebar.</span>"
    )


def out_of_100(prob):
    """A share of futures as a plain count out of 100 that never hides a real risk."""
    if 0 < prob < 0.005:
        return "fewer than 1"
    return f"{round(prob * 100)}"


# Quick picks for the return input, from lower to higher growth. Set through a
# button callback, which runs before the widget is created on the next rerun.
RETURN_PICKS = [
    (5.0, "Lower growth", "an example return before inflation"),
    (7.0, "Middle growth", "an example return before inflation"),
    (10.0, "Higher growth", "an example return before inflation"),
]


def _set_returns(value):
    st.session_state["in_returns"] = value


def render_html(html: str):
    """
    Every ``unsafe_allow_html`` render routes through here. Only ever
    interpolate computed numbers into these strings, never user-supplied text.
    """
    st.markdown(html, unsafe_allow_html=True)


# One-click scenarios for the case studies. Keys/types must match the sidebar
# widgets exactly (int widgets need ints, float widgets floats). Every preset
# uses the allowance estimator so the pension figure is in the same future
# dollars as the salary path; tests/test_case_studies.py checks the copy.
PRESETS = {
    "alice": {
        "label": "Alice: your own account wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 120000, "in_hire_age": 25, "in_retirement_age": 55,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "10, 20",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 30, "in_returns": 10.0,
            "mc_std": 15.0,
        },
    },
    "bob": {
        "label": "Bob: pension wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 65000, "in_hire_age": 40, "in_retirement_age": 60,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 35, "in_returns": 5.0,
            "mc_std": 15.0,
        },
    },
    "carol": {
        "label": "Carol: your own account wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 80000, "in_hire_age": 25, "in_retirement_age": 60,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "15",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 25, "in_returns": 9.0,
            "mc_std": 15.0,
        },
    },
    "dave": {
        "label": "Dave: pension wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 95000, "in_hire_age": 48, "in_retirement_age": 63,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 25, "in_returns": 4.0,
            "mc_std": 15.0,
        },
    },
    "grace": {
        "label": "Grace: pension wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 90000, "in_hire_age": 50, "in_retirement_age": 63,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 25, "in_returns": 7.0,
            "mc_std": 15.0,
        },
    },
    "frank": {
        "label": "Frank: your own account wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 150000, "in_hire_age": 35, "in_retirement_age": 60,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "10, 18",
            "in_promo_pct": 10.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 25, "in_returns": 10.0,
            "mc_std": 15.0,
        },
    },
}


def queue_preset(preset_id):
    """Ask the entry script to load a preset on the next rerun.

    Widget state can only be written before the widget is instantiated, and
    the sidebar widgets render at the top of every run, so a button handler
    (which fires mid-run) parks the preset here and the entry script applies
    it first thing on the rerun.
    """
    st.session_state["_pending_preset"] = preset_id
    st.rerun()


def apply_pending_preset():
    """Apply a queued preset to the sidebar widget state. Call before render_sidebar()."""
    if st.session_state.pop("_restore_requested", False):
        saved = st.session_state.pop("_before_example", {})
        for key in _SHARE_SPEC:
            if key in saved:
                st.session_state[key] = saved[key]
            else:
                st.session_state.pop(key, None)
        st.session_state.pop("_example_label", None)
        st.session_state["_allowance_previous_period"] = st.session_state.get("in_allowance_period", "Yearly")
    preset_id = st.session_state.pop("_pending_preset", None)
    if preset_id:
        if "_before_example" not in st.session_state:
            st.session_state["_before_example"] = {
                k: st.session_state[k] for k in _SHARE_SPEC if k in st.session_state
            }
        preset = PRESETS[preset_id]
        for k, v in preset["values"].items():
            st.session_state[k] = v
        st.session_state["in_plan_age"] = preset["values"]["in_retirement_age"] + preset["values"]["in_retirement_years"]
        st.session_state["_example_label"] = preset["label"]
        st.toast(f"Loaded the scenario: {preset['label']}. The whole page now shows these numbers.", icon="✅")


def restore_previous_inputs():
    st.session_state["_restore_requested"] = True


def convert_manual_period():
    """Changing entry units preserves the same annual pension amount."""
    old = st.session_state.get("_allowance_previous_period", "Yearly")
    new = st.session_state["in_allowance_period"]
    if old != new and "allowance_manual" in st.session_state:
        amount = st.session_state["allowance_manual"]
        st.session_state["allowance_manual"] = amount / 12 if new == "Monthly" else amount * 12
    st.session_state["_allowance_previous_period"] = new


def render_dollar_toggle(inputs, res):
    """Rendered on each page; the entry script reads the value from session_state."""
    st.toggle(
        "Show amounts in today's dollars",
        value=True,
        key="in_real",
        help=(
            f"Charts and summaries: buying power at today's ({CURRENT_YEAR}) prices. "
            "A displayed \\$1,000 means it could buy what \\$1,000 buys today. "
            "Yearly tables and case studies show amounts paid in each year, as labeled. "
            "Turn this off to see every amount as paid in each year instead."
        ),
    )
    rate = res["index_return_pct"]
    inflation_pct = (inputs["inflation"] - 1) * 100
    real_rate = simulation.purchasing_power_return(inputs["index_returns_rate"], inputs["inflation"]) * 100
    if inputs["plan_status"] == "unvested":
        pension_note = "In this scenario you leave before qualifying for a pension, so you get your contributions back instead."
    elif res["retiree_cola_pct"] == 0:
        pension_note = "In this scenario the pension payment stays the same every year."
    else:
        pension_note = f"The pension payment goes up {res['retiree_cola_pct']:.1f}% each year (it follows prices, up to 2%)."
    if inputs["plan_status"] != "unvested" and inputs["retiree_cola"] < inputs["inflation"]:
        loss = -simulation.purchasing_power_return(inputs["retiree_cola"], inputs["inflation"]) * 100
        pension_note += f" Prices rise faster than that, so each payment buys about {loss:.1f}% less every year."
    with st.expander(f"What do today's dollars and {rate:.1f}% growth mean?"):
        st.markdown(
            f"**{rate:.1f}% growth:** \\$100 invested grows to "
            f"\\${inputs['index_returns_rate'] * 100:.2f} in a year. But prices also rise {inflation_pct:.1f}% a year, "
            f"so that \\${inputs['index_returns_rate'] * 100:.2f} only buys what "
            f"\\${inputs['index_returns_rate'] / inputs['inflation'] * 100:.2f} buys today. "
            f"After rising prices, your money really grows about {real_rate:.1f}% a year."
        )
        st.markdown(
            "**Today's dollars** and **real dollars** both mean amounts adjusted for inflation. "
            f"Here, they show buying power at {CURRENT_YEAR} prices. "
            "**Nominal dollars** means the amounts paid or held in each year, with no inflation adjustment. "
            "Both describe the same money in different ways."
        )
        st.markdown(f"**The pension:** {pension_note}")
        st.caption("Investment returns are always entered before inflation. Do not subtract inflation from your return input; the buying-power display already accounts for it.")


def render_sidebar():
    """Render all shared inputs in the sidebar and return them as a dict.

    Called from the entry script on every rerun (i.e. on every page), so the
    widgets keep their state across page switches without any session_state
    pinning.
    """
    with st.sidebar:
        st.header("Your Details")

        with st.expander("Timing Assumptions"):
            st.markdown("""
This calculator operates in annual periods. Within each year:
- **Contributions & deposits**: Made at the end of the year.
- **Withdrawals**: Made at the end of the year.
- **Market returns**: Earned on the balance at the *start* of the year, before that year's deposit or withdrawal.
- **COLA**: Applied to salary at the end of each working year, taking effect the following year. In retirement, the pension's own COLA (inflation, up to 2% a year) is applied at the end of each year, taking effect the following year.
- **Step increases**: Applied at the end of each of your first few working years (set by *Number of Step Raises*), taking effect the following year. If your first step raise comes mid-year, Year 1 is averaged over 6 months at the starting step and 6 months at the next step.
- **Promotions**: Applied at the end of the year you specify, taking effect the following year.
""")

        st.subheader("Career")
        hire_year = int(st.number_input(
            "Year You Were Hired",
            value=CURRENT_YEAR, min_value=CURRENT_YEAR - 60, max_value=CURRENT_YEAR, step=1,
            key="in_hire_year",
            help=(
                "The year your career (and your pension contributions) started. Leave it at this "
                "year to plan a career from scratch. If you were hired years ago, enter that year: "
                "the calculator still runs your whole career from day one."
            ),
        ))
        years_so_far = CURRENT_YEAR - hire_year
        _wage_mode = "My starting wage"
        if years_so_far > 0:
            _wage_mode = st.radio(
                "Which wage do you know?",
                ["My starting wage", "My wage today"],
                horizontal=True,
                key="in_wage_mode",
                help=(
                    "If you don't remember what you were paid when you started, enter what you make "
                    "now. The calculator works backward through your raises to estimate your starting wage."
                ),
            )
        if _wage_mode == "My wage today":
            current_wage = st.number_input(
                "Annual Salary Today, Before Taxes ($)",
                value=120000, min_value=0, max_value=10_000_000, step=2500,
                key="in_current_wage",
                help=f"What you are paid now, in {CURRENT_YEAR}.",
            )
        else:
            starting_wage = st.number_input(
                "Starting Annual Salary, Before Taxes ($)",
                value=120000, min_value=0, max_value=10_000_000, step=2500,
                key="in_wage",
                help=f"Your salary in your first year on the job, in {hire_year} dollars (what you were actually paid then).",
            )
        hire_age = int(st.number_input(
            "Age When Hired",
            value=25, min_value=16, max_value=74, step=1,
            key="in_hire_age",
            help="How old you were (or will be) when you started the job.",
        ))
        retirement_age = int(st.number_input(
            "Age at Retirement",
            value=55, min_value=17, max_value=75, step=1,
            key="in_retirement_age",
            help="Your age on the day you expect to retire.",
        ))
        # Input problems are collected instead of stopping the script here:
        # st.stop() mid-sidebar would skip the widgets below, and Streamlit then
        # forgets their values. Each problem uses a safe stand-in value so the
        # rest of the sidebar still renders; the entry script withholds results.
        problems = []
        work_years = retirement_age - hire_age
        if work_years < 1:
            st.error(
                f"You retire at {retirement_age} but start at {hire_age}. Make your retirement age "
                f"later than the age you were hired to continue."
            )
            problems.append("ages")
            work_years = 1
        else:
            st.caption(
                f"That is {work_years} years of work: from {hire_year} (age {hire_age}) "
                f"to {hire_year + work_years} (age {retirement_age})."
            )
        with st.expander("Salary changes (optional)"):
            cola_increase = st.number_input(
                "Yearly Cost-of-Living Raise (%)",
                value=3.0, min_value=0.0, max_value=5.5, step=0.1,
                key="in_cola",
                help="Annual salary adjustment, typically between 2-3.5%. Set to 0 for plans with no COLA. This is for your salary while working; the pension's own COLA in retirement follows inflation (see Expected Inflation below)."
            ) / 100 + 1
            step_increase = st.number_input(
                "Step Increase (%)",
                value=5.5, min_value=0., max_value=50.0, step=0.1,
                key="in_step",
                help="Raise from each step on your pay scale."
            ) / 100 + 1
            step_count = st.number_input(
                "Number of Step Raises",
                value=4, min_value=0, max_value=20, step=1,
                key="in_step_count",
                help="How many step raises you get before reaching the top of your pay scale. One raise is applied at the end of each of your first this-many years.",
            )
            first_step_midyear = st.checkbox(
                "First step raise comes mid-year",
                value=True,
                key="in_step_midyear",
                help="Check this if your first step raise takes effect partway through Year 1 (for example, after a 6-month probation). Year 1 is then averaged half at your starting step and half at the next step.",
            )
            st.caption("Promotions are optional. Enter 10 for a raise after your tenth working year. Leave blank for none.")
            promotion_years_input = st.text_input(
                "Promotions: Years After You Were Hired",
                value="10, 20",
                key="in_promo_years",
                help="Comma-separated year numbers within your career when you expect a promotion (e.g. 10, 20). Leave blank if none."
            )
            # Parse promotion years exactly once. Only plain ASCII digits count:
            # str.isdigit() also accepts characters like "²" that int() rejects.
            _promo_tokens = [t.strip() for t in promotion_years_input.split(",") if t.strip()]
            _promo_bad = [t for t in _promo_tokens if not re.fullmatch(r"[0-9]{1,3}", t)]
            _promo_good = tuple(int(t) for t in _promo_tokens if re.fullmatch(r"[0-9]{1,3}", t))
            _promo_oob = [y for y in _promo_good if y < 1 or y > int(work_years)]
            promotion_years = tuple(y for y in _promo_good if 1 <= y <= int(work_years))
            if _promo_bad:
                st.error(f"Can't parse promotion year(s): {', '.join(_promo_bad)}. Enter whole numbers only, then results will update.")
                problems.append("promotions")
            elif _promo_oob and "ages" not in problems:
                st.warning(f"Promotion year(s) {', '.join(str(y) for y in _promo_oob)} fall outside your {int(work_years)}-year career, so they are left out.")
            promotion_increase = st.number_input(
                "Promotion Increase (%)",
                value=8.0, min_value=0.0, max_value=100.0, step=1.,
                key="in_promo_pct",
                help="Expected salary bump each time you are promoted."
            ) / 100 + 1
        st.caption(
            f"Salary assumptions: {(cola_increase - 1) * 100:.1f}% yearly raise, "
            f"{int(step_count)} step raises, "
            + (f"promotions after career years {', '.join(map(str, promotion_years))}." if promotion_years else "no promotions.")
        )

        if _wage_mode == "My wage today":
            # This calendar year is career year (years_so_far + 1). Undo every
            # raise up to it (COLA, steps, promotions) to recover the starting wage.
            _year_now = years_so_far + 1
            if _year_now > int(work_years):
                if "ages" not in problems:
                    st.error(
                        f"Hired in {hire_year}, you would have finished your {int(work_years)}-year career "
                        f"already. Pick a later retirement age, or enter your starting wage instead."
                    )
                problems.append("wage")
                starting_wage = current_wage
            else:
                _growth = simulation.salary_schedule(
                    1.0, _year_now, cola_increase, step_increase, promotion_years,
                    promotion_increase, int(step_count), first_step_midyear)[-1]
                starting_wage = current_wage / _growth
                st.caption(
                    f"That works out to a starting wage of about ${starting_wage:,.0f} in {hire_year}, "
                    f"using the raises you entered above."
                )

        st.subheader("Pension")
        st.caption(
            f"Pension estimates follow the plan's rules for members hired in "
            f"{simulation.PLAN_FIRST_HIRE_YEAR} or later."
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
        if hire_year < simulation.PLAN_FIRST_HIRE_YEAR:
            st.warning(
                f"This calculator is designed for members hired in or after "
                f"{simulation.PLAN_FIRST_HIRE_YEAR}. It does not model the pension rules for members "
                f"hired earlier. Entering a manual pension amount does not change when payments start "
                f"or how they increase, so the results may not match your pension."
            )
        pension_contribution_rate = st.number_input(
            "Pension Contribution Rate (%)",
            value=10.0, min_value=0.0, max_value=100.0, step=1.,
            key="in_contrib",
            help="Percentage of your salary automatically deducted and contributed to the pension system each year."
        ) / 100
        if abs(pension_contribution_rate * 100 - simulation.PLAN_CONTRIBUTION_PCT) > 1e-9:
            st.caption(
                f"Members of this plan contribute {simulation.PLAN_CONTRIBUTION_PCT:g}%. A different rate "
                f"changes what goes into your own account, but not the pension formula."
            )

        st.markdown("**Your Pension**")

        _allowance_mode = st.radio(
            "How to set allowance",
            ["Estimate for me", "Enter manually"],
            horizontal=True,
            key="in_allowance_mode",
            label_visibility="collapsed",
        )
        manual_override = (_allowance_mode == "Enter manually")

        # Inflation drives the retiree COLA and the today's-dollars views, so it
        # is read before the allowance captions that use it (widget in Retirement).
        inflation = 1 + st.session_state.get("in_inflation", 2.5) / 100

        # The plan's eligibility rules apply in both modes. Entering the amount
        # by hand replaces only the dollar figure, never when payments start or
        # whether they get a COLA.
        _fas = compute_fas(starting_wage, int(work_years), cola_increase, step_increase,
                           promotion_years, promotion_increase,
                           int(step_count), first_step_midyear)
        plan = simulation.plan_benefit(int(work_years), int(retirement_age), _fas)
        # Payments are made at the end of each year, like every other cash flow
        # here, so the first one lands at the end of the first year it is due.
        # This is the one timing used for every today's-dollars conversion.
        _first_pay_year = hire_year + int(work_years) + plan["deferral_years"]
        _years_to_first_pay = int(work_years) + plan["deferral_years"] + 1 - years_so_far

        if not manual_override:
            starting_allowance = plan["allowance"]
            # The value is pushed through session_state (not ``value=``) so a
            # keyed, disabled widget always shows the freshly computed figure.
            st.session_state["allowance_formula"] = round(starting_allowance)
            st.number_input(
                f"Yearly Pension in {_first_pay_year} Dollars ($)",
                min_value=0,
                step=500,
                disabled=True,
                key="allowance_formula",
                help=(
                    "Years of Service × Final Average Salary (highest 3 consecutive years) "
                    "× Retirement Factor × Early Retirement Reduction Factor, capped at 80% of "
                    "Final Average Salary. The factor and any reduction follow the plan's rules "
                    "for your age and years of service. Switch to 'Enter manually' to override."
                ),
            )
        else:
            st.session_state.setdefault("_allowance_previous_period", st.session_state.get("in_allowance_period", "Yearly"))
            period = st.radio(
                "Enter a monthly or yearly pension amount",
                ["Yearly", "Monthly"], horizontal=True,
                key="in_allowance_period", on_change=convert_manual_period,
            )
            manual_allowance = st.number_input(
                "Pension Payment Before Taxes ($)",
                value=70000.0 if period == "Yearly" else 70000.0 / 12,
                min_value=0.0,
                max_value=10_000_000.0 if period == "Yearly" else 10_000_000.0 / 12,
                step=100.0,
                format="%.2f",
                key="allowance_manual",
                help=(
                    "Your pension payment in its first year, before taxes. Find this from your plan's retirement "
                    "estimator. When payments start and how they grow still follow the plan's rules."
                ),
            )
            if period == "Monthly":
                manual_allowance *= 12
            st.caption(f"That is ${manual_allowance:,.0f} a year, or ${manual_allowance / 12:,.0f} a month, before taxes.")
            _basis = st.radio(
                "This amount is in",
                ["Today's dollars", "Dollars at retirement"],
                format_func=lambda o: f"Buying power at today's ({CURRENT_YEAR}) prices" if o == "Today's dollars" else f"Amount paid when payments start ({_first_pay_year})",
                key="in_allowance_basis",
                help=(
                    "Check how your pension estimate labels its amount. Choose buying power if it says "
                    "today's dollars or inflation-adjusted. Choose amount paid if it gives the payment "
                    "expected in the year payments start. If the estimate does not say, check with your plan. "
                    "This choice describes your input; the display switch above only changes how results are shown."
                ),
            )
            if _basis == "Today's dollars":
                starting_allowance = simulation.to_retirement_dollars(
                    manual_allowance, _years_to_first_pay, inflation)
                if plan["status"] != "unvested":
                    st.caption(f"To have that buying power, the first year's payments would total about ${starting_allowance:,.0f} in {_first_pay_year}, using your inflation assumption.")
            else:
                starting_allowance = manual_allowance

        if plan["status"] == "unvested":
            _refund = simulation.refund_with_interest(
                [s * pension_contribution_rate for s in simulation.salary_schedule(
                    starting_wage, int(work_years), cola_increase, step_increase,
                    promotion_years, promotion_increase, int(step_count), first_step_midyear)])
            st.warning(
                f"With {int(work_years)} years of service you would not vest, so there is no "
                f"lifetime pension{' (the amount above is not used)' if manual_override else ''}. "
                f"Instead your contributions are refunded with "
                f"{simulation.PLAN_REFUND_INTEREST_PCT:g}% interest a year: about ${_refund:,.0f} when you leave."
            )
            starting_allowance = 0.0
        else:
            _start_age = int(retirement_age) + plan["deferral_years"]
            _cola_pct = (min((inflation - 1) * 100, simulation.PLAN_RETIREE_COLA_CAP_PCT)
                         if plan["cola_applies"] else 0.0)
            if not manual_override:
                _rule = f"{plan['factor_pct']:g}% per year of service"
                if plan["reduction"] < 1:
                    _rule += f", reduced to {plan['reduction'] * 100:.1f}% for retiring before 55"
                if plan["capped"]:
                    _rule += ", capped at 80% of your final average salary"
                _today = starting_allowance / inflation ** _years_to_first_pay
                st.caption(f"{_rule}. The first year's pension would buy about what ${_today:,.0f} buys today ({CURRENT_YEAR} prices).")
            else:
                st.caption(
                    f"Under the plan's rules, payments start at age {_start_age} and "
                    + (f"rise {_cola_pct:.1f}% a year." if _cola_pct else "stay the same each year (no COLA).")
                )
            if plan["status"] == "deferred":
                st.warning(
                    f"Without 30 years of service you can't start a pension before age "
                    f"{simulation.PLAN_FULL_AGE}. Leaving at {int(retirement_age)} gives a deferred pension "
                    f"from age {simulation.PLAN_FULL_AGE} with no COLA, so neither option pays anything for "
                    f"your first {plan['deferral_years']} years of retirement."
                )

        st.subheader("Retirement")
        st.session_state.setdefault("in_plan_age", retirement_age + st.session_state.get("in_retirement_years", 30))
        plan_age = st.number_input(
            "Plan Through Age",
            min_value=18, max_value=135, step=1,
            key="in_plan_age",
            help="How long should this comparison cover? This is a planning assumption, not a prediction of how long you will live."
        )
        retirement_years = int(plan_age) - retirement_age
        if not 1 <= retirement_years <= 60:
            st.error(f"Choose an ending age from {retirement_age + 1} to {min(135, retirement_age + 60)} to model 1 to 60 years of retirement.")
            problems.append("horizon")
            retirement_years = min(60, max(1, retirement_years))
        st.session_state["in_retirement_years"] = retirement_years
        st.caption(f"This comparison covers {retirement_years} years of retirement, from age {retirement_age} to {int(plan_age)}.")
        inflation_pct = st.number_input(
            "Yearly Rise in Prices (Inflation %)",
            value=2.5, min_value=0.0, max_value=10.0, step=0.1,
            key="in_inflation",
            help=(
                "How much you assume prices rise each year. For example, at 2.5%, a $100 grocery bill "
                "becomes $102.50 next year. Eligible pension payments rise with this rate, capped at "
                f"{simulation.PLAN_RETIREE_COLA_CAP_PCT:g}% a year. It also converts amounts to today's buying power. "
                "Salary raises are entered separately."
            ),
        )
        st.markdown("**Try an example yearly return (before inflation):**")
        for col, (value, name, why) in zip(st.columns(len(RETURN_PICKS)), RETURN_PICKS):
            col.button(f"{value:g}%", key=f"pick_{value:g}", on_click=_set_returns, help=f"{name}: {why}",
                       args=(value,), width="stretch")
        st.caption(
            "The starting 10% is an example, not a forecast. Try 5%, 7%, and 10% to see how much the result changes. "
            "All are before inflation, not investment recommendations. "
            "The buttons change only the return. Market swings are set separately on the second page."
        )
        _show_real = st.session_state.get("in_real", True)
        if _show_real:
            _after = [simulation.purchasing_power_return(1 + v / 100, 1 + inflation_pct / 100) * 100
                      for v, _, _ in RETURN_PICKS]
            st.caption(
                f"After {inflation_pct:.1f}% inflation, those are about "
                + ", ".join(f"{a:.1f}%" for a in _after[:-1]) + f", and {_after[-1]:.1f}% a year."
            )
        index_returns_rate = (
            st.number_input(
                "Yearly Investment Return Before Inflation (%)",
                value=10.0,
                min_value=0.0,
                max_value=25.0,
                step=0.5,
                key="in_returns",
                help=(
                    "The growth you assume before adjusting for rising prices. Do not subtract inflation here. "
                    "The first page uses this exact return every year. The market-swings page uses it as the "
                    "middle yearly return, with good and bad years around it. It is not a guaranteed return."
                ),
            )
            / 100
            + 1
        )
        if _show_real:
            _real_return = simulation.purchasing_power_return(index_returns_rate, 1 + inflation_pct / 100) * 100
            st.caption(f"About {_real_return:.1f}% a year after {inflation_pct:.1f}% inflation.")

    retiree_cola_pct = min(inflation_pct, simulation.PLAN_RETIREE_COLA_CAP_PCT)
    if not plan["cola_applies"]:
        retiree_cola_pct = 0.0

    return {
        "starting_wage": starting_wage,
        "work_years": int(work_years),
        "retirement_age": int(retirement_age),
        "hire_year": hire_year,
        "cola_increase": cola_increase,
        "step_increase": step_increase,
        "promotion_years": promotion_years,
        "promotion_increase": promotion_increase,
        "step_count": int(step_count),
        "first_step_midyear": bool(first_step_midyear),
        "pension_contribution_rate": pension_contribution_rate,
        "starting_allowance": starting_allowance,
        "retirement_years": int(retirement_years),
        "index_returns_rate": index_returns_rate,
        "inflation": 1 + inflation_pct / 100,
        "retiree_cola": 1 + retiree_cola_pct / 100,
        "deferral_years": plan["deferral_years"],
        "plan_status": plan["status"],
        "allowance_source": "manual" if manual_override else "estimate",
        "problems": problems,
    }


def _engine_args(inputs):
    """Positional arguments shared by every simulation entry point."""
    return (
        inputs["starting_wage"], inputs["work_years"], inputs["cola_increase"],
        inputs["step_increase"], inputs["promotion_years"], inputs["promotion_increase"],
        inputs["pension_contribution_rate"], inputs["starting_allowance"],
        inputs["retirement_years"],
    )


def _engine_kwargs(inputs):
    return {
        "step_count": inputs["step_count"],
        "first_step_midyear": inputs["first_step_midyear"],
        "retiree_cola": inputs["retiree_cola"],
        "deferral_years": inputs["deferral_years"],
    }


def compute_results(inputs):
    """Run the flat-rate simulation and derive everything both pages display."""
    result = run_simulation(*_engine_args(inputs), inputs["index_returns_rate"],
                            **_engine_kwargs(inputs))

    personal_fund_values = result["personal_fund_values"]

    # First retirement year where your own account is depleted
    depletion_year = next(
        (k for k in range(1, inputs["retirement_years"] + 1)
         if simulation.ran_short(personal_fund_values[inputs["work_years"] + k])),
        None,
    )

    breakeven_rate = compute_breakeven_rate(*_engine_args(inputs), **_engine_kwargs(inputs))

    years_covered = inputs["retirement_years"] if depletion_year is None else depletion_year - 1

    # Unvested members get their contributions back with interest instead of
    # a pension. The refund and your own account grow from the same deposits,
    # so the fair comparison is the two amounts on the day you leave.
    refund = None
    if inputs["plan_status"] == "unvested":
        contributions = result["yearly_data"]["Pension Contribution"].iloc[:inputs["work_years"]]
        refund = simulation.refund_with_interest(contributions.tolist())

    return {
        **result,
        "refund": refund,
        "account_at_leaving": personal_fund_values[inputs["work_years"]],
        "depletion_year": depletion_year,
        "breakeven_rate": breakeven_rate,
        "years_covered": years_covered,
        # Display-only percentages
        "index_return_pct": (inputs["index_returns_rate"] - 1) * 100,
        "cola_pct": (inputs["cola_increase"] - 1) * 100,
        "retiree_cola_pct": (inputs["retiree_cola"] - 1) * 100,
        "step_pct": (inputs["step_increase"] - 1) * 100,
        "promotion_pct": (inputs["promotion_increase"] - 1) * 100,
    }


def get_monte_carlo(inputs, std_pct, n_simulations=1000):
    """Cached Monte Carlo run for the current inputs at the given volatility (%)."""
    return run_monte_carlo(
        *_engine_args(inputs),
        mean_return=inputs["index_returns_rate"] - 1,
        std_return=std_pct / 100.0,
        n_simulations=n_simulations,
        **_engine_kwargs(inputs),
    )


def calendar_years_for(inputs):
    """Calendar year of each chart point (W0 and year 1 are both the hire year)."""
    n = inputs["work_years"] + inputs["retirement_years"] + 1
    return [inputs["hire_year"] + max(i - 1, 0) for i in range(n)]


def ages_for(inputs):
    """Age at the end of each simulated year: hire age for W0, then one per year."""
    hire_age = inputs["retirement_age"] - inputs["work_years"]
    return [hire_age + i for i in range(inputs["work_years"] + inputs["retirement_years"] + 1)]


def _years_after_now(inputs, i):
    """Years from the start of this calendar year to the end of chart point ``i``."""
    return i - (CURRENT_YEAR - inputs["hire_year"])


def _deflators(inputs, n_points):
    """Divide by these to turn end-of-year amounts into this year's dollars.

    Points after today shrink by inflation; for a career that started years
    ago, points before today grow instead (the exponent is negative).
    """
    return np.array([inputs["inflation"] ** _years_after_now(inputs, i) for i in range(n_points)])


def deflate_results(res, inputs):
    """A copy of the flat-rate results with every dollar amount in this year's dollars.

    Each end-of-year amount is divided by inflation compounded to that year.
    Running totals are re-summed from the deflated yearly amounts, so they stay
    true sums. Rates (return, break-even) are unchanged. The year-by-year
    tables keep future dollars so each row still adds up.
    """
    df = res["yearly_data"].copy()
    d = _deflators(inputs, len(df) + 1)[1:]
    nominal_start = df["Start Balance"].to_numpy()
    nominal_balance = df["Balance"].to_numpy()
    for col in ("Salary", "Start Balance", "Pension Contribution", "Pension Redeemed",
                "Market Returns", "Balance"):
        df[col] = df[col].to_numpy() / d
    # Below $0 the balance is a running total of unpaid income. Each year's
    # unpaid payment is converted in its own year, so the shortfall is not
    # shrunk as if every missed payment happened at the very end.
    real_balance = df["Balance"].to_numpy().copy()
    for i in range(len(df)):
        if nominal_start[i] < 0:
            unpaid = nominal_start[i] - nominal_balance[i]
            real_balance[i] = real_balance[i - 1] - unpaid / d[i]
    df["Balance"] = real_balance
    df["Pension Contribution Total"] = df["Pension Contribution"].cumsum()
    df["Pension Redeemed Total"] = df["Pension Redeemed"].cumsum()
    working = df["Year"].str.startswith("W")
    df.loc[~working, "Pension Contribution Total"] = 0.0
    out = dict(res)
    out["yearly_data"] = df
    out["personal_fund_values"] = [0] + df["Balance"].tolist()
    out["pension_fund_values"] = [0] + df["Pension Redeemed Total"].tolist()
    out["pension_contribution_total"] = float(df["Pension Contribution"].sum())
    out["pension_redeemed_total"] = float(df["Pension Redeemed"].sum())
    out["personal_balance"] = float(df["Balance"].iloc[-1])
    out["account_at_leaving"] = out["personal_fund_values"][inputs["work_years"]]
    if res.get("refund") is not None:
        out["refund"] = res["refund"] / _deflators(inputs, inputs["work_years"] + 1)[-1]
    out["real_dollars"] = True
    return out


def deflate_mc(mc, inputs):
    """Monte Carlo outputs in this year's dollars (same deflators as the flat path)."""
    d = _deflators(inputs, mc["percentiles"].shape[1])
    out = dict(mc)
    out["percentiles"] = mc["percentiles"] / d
    out["median_path"] = mc["median_path"] / d
    out["final_balances"] = mc["final_balances"] / d[-1]
    out["balances_at_leaving"] = mc["balances_at_leaving"] / d[inputs["work_years"]]
    return out


def dollars_note(res):
    """Suffix for chart titles saying which dollars are shown."""
    return f" (buying power at {CURRENT_YEAR} prices)" if res.get("real_dollars") else " (amounts in each year)"


# --- Shareable links ----------------------------------------------------------------
# Every sidebar input (plus the display toggle and the swing slider) is mirrored
# into the page URL, so a copied link reopens the same scenario. Values are
# parsed and range-checked here before they touch widget state.
_SHARE_SPEC = {
    "in_hire_year": (int, CURRENT_YEAR - 60, CURRENT_YEAR),
    "in_wage_mode": (["My starting wage", "My wage today"], None, None),
    "in_current_wage": (int, 0, 10_000_000),
    "in_wage": (int, 0, 10_000_000),
    "in_hire_age": (int, 16, 74),
    "in_retirement_age": (int, 17, 75),
    "in_cola": (float, 0.0, 5.5),
    "in_step": (float, 0.0, 50.0),
    "in_step_count": (int, 0, 20),
    "in_step_midyear": (bool, None, None),
    "in_promo_years": (str, None, None),
    "in_promo_pct": (float, 0.0, 100.0),
    "in_contrib": (float, 0.0, 100.0),
    "in_allowance_mode": (["Estimate for me", "Enter manually"], None, None),
    "allowance_manual": (float, 0, 10_000_000),
    "in_allowance_period": (["Yearly", "Monthly"], None, None),
    "in_allowance_basis": (["Today's dollars", "Dollars at retirement"], None, None),
    "in_retirement_years": (int, 1, 60),
    "in_plan_age": (int, 18, 135),
    "in_inflation": (float, 0.0, 10.0),
    "in_returns": (float, 0.0, 25.0),
    "in_real": (bool, None, None),
    "mc_std": (float, 0.0, 30.0),
}


def _param_name(key):
    return key.removeprefix("in_")


def _parse_param(raw, spec):
    kind, lo, hi = spec
    if isinstance(kind, list):
        return raw if raw in kind else None
    if kind is bool:
        return {"true": True, "false": False}.get(raw.lower())
    if kind is str:
        return raw[:100]
    try:
        number = float(raw)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < lo or number > hi:
        return None
    if kind is int:
        if number != int(number):
            return None
        return int(number)
    return number


def apply_query_params():
    """Load inputs from the URL once per session, before any widget renders."""
    if st.session_state.get("_qp_applied"):
        return
    st.session_state["_qp_applied"] = True
    if not st.query_params:
        return
    for key, spec in _SHARE_SPEC.items():
        raw = st.query_params.get(_param_name(key))
        if raw is None:
            continue
        value = _parse_param(raw, spec)
        if value is not None:
            st.session_state[key] = value
    manual_limit = 10_000_000 / (12 if st.session_state.get("in_allowance_period") == "Monthly" else 1)
    if st.session_state.get("allowance_manual", 0) > manual_limit:
        st.session_state.pop("allowance_manual", None)
    if "in_plan_age" not in st.session_state and "in_retirement_years" in st.session_state:
        st.session_state["in_plan_age"] = st.session_state.get("in_retirement_age", 55) + st.session_state["in_retirement_years"]
    # Links made before "Age When Hired" existed carry years of work instead.
    if st.query_params.get("hire_age") is None:
        hire_age = legacy_hire_age(st.query_params.get("work_years"),
                                   st.session_state.get("in_retirement_age", 55))
        if hire_age is not None:
            st.session_state["in_hire_age"] = hire_age
    # The address bar is cleared once the values are loaded, so it never keeps
    # showing salary figures; links are made on request (render_share_section).
    st.query_params.clear()


def legacy_hire_age(work_years_raw, retirement_age):
    """Hire age implied by an old link's ``work_years``, or None if unusable."""
    if work_years_raw is None:
        return None
    try:
        years = float(work_years_raw)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(years) or years != int(years):
        return None
    hire_age = int(retirement_age) - int(years)
    lo, hi = _SHARE_SPEC["in_hire_age"][1:]
    return hire_age if lo <= hire_age <= hi else None


def active_share_params(inputs):
    """URL parameters for the inputs that are actually in use right now.

    Values for hidden choices (for example a manual pension amount while the
    estimate is selected) are left out, so a link never carries more than it
    needs to.
    """
    keys = ["in_hire_year", "in_hire_age", "in_retirement_age", "in_cola", "in_step",
            "in_step_count", "in_step_midyear", "in_promo_years", "in_promo_pct", "in_contrib",
            "in_allowance_mode", "in_plan_age", "in_inflation", "in_returns", "in_real",
            "mc_std"]
    today_mode = (inputs["hire_year"] < CURRENT_YEAR
                  and st.session_state.get("in_wage_mode") == "My wage today")
    if inputs["hire_year"] < CURRENT_YEAR:
        keys.append("in_wage_mode")
    keys.append("in_current_wage" if today_mode else "in_wage")
    if inputs["allowance_source"] == "manual":
        keys += ["allowance_manual", "in_allowance_basis", "in_allowance_period"]
    return {_param_name(k): str(st.session_state[k]) for k in keys if k in st.session_state}


def share_link(inputs):
    """A full link that reopens the calculator with the current inputs."""
    base = ""
    try:
        parts = urllib.parse.urlsplit(st.context.url or "")
        if parts.scheme and parts.netloc:
            base = f"{parts.scheme}://{parts.netloc}{parts.path}"
    except Exception:
        base = ""
    return f"{base}?{urllib.parse.urlencode(active_share_params(inputs))}"


def render_share_section(inputs):
    """Sidebar control that makes a shareable link only when asked."""
    with st.sidebar:
        st.subheader("Share These Inputs")
        if st.button("Create a shareable link", key="make_share_link"):
            st.session_state["_show_share_link"] = True
        if st.session_state.get("_show_share_link"):
            st.code(share_link(inputs), language=None, wrap_lines=True)
            st.caption(
                "Copy this link to share or come back later. It includes your salary and pension "
                "assumptions, so anyone with the link can see them. It updates as you change inputs."
            )


def chart_title(text):
    """Chart titles go in page text, which wraps, rather than inside the plot,
    where long titles are cut off on phones."""
    st.markdown(f"**{text}**")


def fund_chart_title(res, title=None):
    if title is None:
        title = f"Your account over time, at a steady {res['index_return_pct']:.1f}% a year"
    return title + dollars_note(res)


def build_fund_chart(inputs, res, show_ref_line, mc_pcts=None, title=None,
                     verdict_annotation=False, show_flat_line=True):
    """Nonnegative account balances, with on-chart labels stating the verdict."""
    years = res["years"]
    personal_fund_values = [max(v, 0.0) for v in res["personal_fund_values"]]
    pension_fund_values = res["pension_fund_values"]
    yearly_data = res["yearly_data"]
    work_years = inputs["work_years"]
    index_return_pct = res["index_return_pct"]
    # The x-axis is age. Ages are unique and increasing (hire age at W0, then
    # one per year), so they double as the plot positions.
    ages = ages_for(inputs)

    # Adaptive x-axis
    total_years = len(years)
    x_tick_step = max(5, int(math.ceil(total_years / 12 / 5) * 5))

    # Adaptive y-axis. When Monte Carlo bands are shown, the range also covers
    # the middle 50% band (25th-75th percentiles) so the "most likely" region
    # is fully visible; the extreme-luck tails (5th/95th) are allowed to clip
    # rather than letting a 20x-lucky path squash the flat line into the
    # bottom of the chart.
    all_values = [v for v in personal_fund_values if v is not None] if show_flat_line else [0.0]
    _yearly_payouts = [0.0] + res["yearly_data"]["Pension Redeemed"].tolist()
    if show_ref_line:
        all_values = all_values + _yearly_payouts
    if mc_pcts is not None:
        all_values = all_values + list(mc_pcts[1]) + list(mc_pcts[2])
    data_min = min(all_values, default=0)
    data_max = max(all_values, default=1)
    data_range = max(data_max - data_min, 1)
    raw_interval = data_range / 10
    magnitude = 10 ** math.floor(math.log10(raw_interval))
    normalized = raw_interval / magnitude
    if normalized <= 1:
        nice = 1
    elif normalized <= 2:
        nice = 2
    elif normalized <= 2.5:
        nice = 2.5
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10
    y_tick_interval = nice * magnitude

    fig = go.Figure()

    _xf = list(ages)
    _xr = list(ages)[::-1]

    if mc_pcts is not None:
        fig.add_trace(go.Scatter(
            x=_xf + _xr,
            y=list(mc_pcts[0]) + list(mc_pcts[1])[::-1],
            fill="toself", fillcolor="rgba(220,38,38,0.18)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Unlucky futures", hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=_xf + _xr,
            y=list(mc_pcts[1]) + list(mc_pcts[2])[::-1],
            fill="toself", fillcolor="rgba(59,130,246,0.18)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Middle half of futures (most likely)", hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=_xf + _xr,
            y=list(mc_pcts[2]) + list(mc_pcts[3])[::-1],
            fill="toself", fillcolor="rgba(22,163,74,0.18)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Lucky futures", hoverinfo="skip",
        ))

    # Hover arrays
    _deposits = [0.0] + yearly_data["Pension Contribution"].tolist()
    _withdrawals = [0.0] + yearly_data["Pension Redeemed"].tolist()
    _returns = [0.0] + yearly_data["Market Returns"].tolist()
    _cal = calendar_years_for(inputs)
    _personal_customdata = list(zip(_deposits, _withdrawals, _returns, years, _cal))

    fig.add_trace(go.Scatter(
        x=ages,
        # Each year's payment (what the label promises), with the running
        # total in the hover; plotting the running total dwarfed everything.
        y=_yearly_payouts,
        mode="lines+markers",
        name="Pension paid each year (same for both)",
        line=dict(color="#A855F7", width=2),
        marker=dict(color="#A855F7", size=5, symbol="circle"),
        customdata=list(zip(pension_fund_values, years, _cal)),
        hovertemplate=(
            "<b>Age %{x}</b> · %{customdata[2]} (year %{customdata[1]})<br>"
            "This year paid out: $%{y:,.0f}<br>"
            "Running total paid out: $%{customdata[0]:,.0f}"
            "<extra></extra>"
        ),
        visible=show_ref_line,
    ))

    fig.add_trace(go.Scatter(
        x=ages,
        y=personal_fund_values,
        mode="lines+markers",
        name=f"Steady {index_return_pct:.1f}% before inflation",
        line=dict(color="#0D9488", width=3),
        visible=show_flat_line,
        customdata=_personal_customdata,
        hovertemplate=(
            "<b>Age %{x}</b> · %{customdata[4]} (year %{customdata[3]})<br>"
            "Deposit this year: $%{customdata[0]:,.0f}<br>"
            "Withdrawal this year: $%{customdata[1]:,.0f}<br>"
            "Market returns this year: $%{customdata[2]:,.0f}<br>"
            "Your account's balance: $%{y:,.0f}"
            "<extra></extra>"
        ),
    ))

    _y_pad = data_range * 0.12
    fig.update_layout(
        xaxis_title="Your age",
        yaxis_title="Account balance ($)",
        xaxis=dict(
            tickmode="array",
            tickvals=[ages[i] for i in range(0, len(ages), x_tick_step)],
            tickfont=dict(size=12),
            showgrid=True,
            gridcolor="lightgray",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="lightgray",
            dtick=y_tick_interval,
            tickformat=".2s",
            separatethousands=True,
            range=[0, data_max + _y_pad],
        ),
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
        margin=dict(l=15, r=15, t=20, b=40),
        height=420,
    )

    fig.add_vrect(
        x0=ages[0], x1=ages[work_years],
        fillcolor="rgba(0,0,0,0)", layer="below", line_width=0,
        annotation_text="<b>Working Years</b>", annotation_position="top left",
        annotation=dict(font_size=13, font_color="#1E3A5F",
                        bgcolor="rgba(255,255,255,0.75)", borderpad=5),
    )
    fig.add_vrect(
        x0=ages[work_years], x1=ages[-1],
        fillcolor="rgba(148,163,184,0.08)", layer="below", line_width=0,
        annotation_text="<b>Retirement Years</b>", annotation_position="top left",
        annotation=dict(font_size=13, font_color="#7C2D12",
                        bgcolor="rgba(255,255,255,0.75)", borderpad=5),
    )
    fig.add_vline(x=ages[work_years], line_width=2, line_dash="dash", line_color="#DC2626")
    _raw_values = res["personal_fund_values"]
    _fund_depletes = simulation.ran_short(min(_raw_values))
    fig.add_hline(y=0, line_width=1, line_color="#666666",
                  annotation_text="$0 = your account is empty" if _fund_depletes else "$0",
                  annotation_position="bottom right")

    if verdict_annotation:
        if _fund_depletes:
            _dep_idx = next(i for i, v in enumerate(_raw_values) if simulation.ran_short(v))
            fig.add_annotation(
                x=ages[_dep_idx], y=0,
                text=f"<b>✗ Runs out by age {ages[_dep_idx]}</b>",
                showarrow=True, arrowhead=2, arrowcolor="#DC2626",
                ax=-110, ay=-60,
                font=dict(size=13, color="#DC2626"),
                bgcolor="rgba(255,255,255,0.85)", borderpad=4,
            )
        else:
            fig.add_annotation(
                x=ages[-1], y=personal_fund_values[-1],
                text=f"<b>✓ ${personal_fund_values[-1]:,.0f} left over</b>",
                showarrow=True, arrowhead=2, arrowcolor="#0D9488",
                ax=-90, ay=-40,
                font=dict(size=13, color="#0D9488"),
                bgcolor="rgba(255,255,255,0.85)", borderpad=4,
            )
    return fig


def account_payment_table(df):
    """Present actual account cash flows separately from income it could not pay."""
    table = df.copy()
    table["Start Balance"] = table["Start Balance"].clip(lower=0)
    available = table["Start Balance"] + table["Market Returns"]
    table["Account Withdrawal"] = np.minimum(available, table["Pension Redeemed"])
    table["Income Unpaid"] = table["Pension Redeemed"] - table["Account Withdrawal"]
    table["Balance"] = table["Balance"].clip(lower=0)
    return table


def render_breakdown_table(df, phase_prefix, rename_map, balance_col=None):
    """Render one side of the year-over-year breakdown."""
    table = df[df["Year"].str.startswith(phase_prefix)].copy()
    table = table.rename(columns=rename_map)

    money_cols = [c for c in table.columns if c not in ("Year", "Age")]

    # These sets don't depend on `col`; compute once, not per column.
    renamed_running = {rename_map.get(k, k) for k in (
        "Pension Contribution Total", "Pension Redeemed Total")}
    renamed_balance = {rename_map.get(k, k) for k in ("Balance",)}
    total_row = {"Year": "Total", **({"Age": None} if "Age" in table.columns else {})}
    for col in money_cols:
        if col in renamed_running or col in renamed_balance:
            total_row[col] = table[col].iloc[-1] if len(table) else 0.0
        elif col == rename_map.get("Salary", "Salary") or col == rename_map.get("Start Balance", "Start Balance"):
            total_row[col] = float("nan")
        else:
            total_row[col] = table[col].sum()
    table = pd.concat([table, pd.DataFrame([total_row])], ignore_index=True)

    def _highlight_negative(val):
        if isinstance(val, (int, float)) and pd.notna(val) and val < 0:
            return "color: #d62728; font-weight: 600;"
        return ""

    def _bold_total(row):
        return ["font-weight: 700;" if row["Year"] == "Total" else "" for _ in row]

    styler = table.style.format("${:,.0f}", subset=money_cols, na_rep="-")
    if "Age" in table.columns:
        styler = styler.format("{:.0f}", subset=["Age"], na_rep="")
    styler = styler.apply(_bold_total, axis=1)
    if balance_col is not None:
        styler = styler.map(_highlight_negative, subset=[balance_col])
    return styler


def render_feedback_form(page_name):
    """Shared feedback form. Reads current inputs/results from session_state.

    ``page_name`` and the current Monte Carlo context are recorded with each
    submission so feedback about the risk page can be read alongside the
    volatility and depletion numbers the user was actually looking at.
    """
    inputs = st.session_state["_inputs"]
    # Feedback rows are logged in future dollars regardless of the display toggle.
    res = st.session_state["_results_nominal"]

    st.divider()
    st.header("Share Your Feedback")
    st.caption("What would make this calculator more useful? What's missing, confusing, or surprising?")

    if "feedback_key" not in st.session_state:
        st.session_state.feedback_key = 0
    if "feedback_success" not in st.session_state:
        st.session_state.feedback_success = False
    if "feedback_last_submit" not in st.session_state:
        st.session_state.feedback_last_submit = 0.0

    with st.form("feedback_form"):
        feedback_text = st.text_area(
            "Your feedback",
            height=120,
            max_chars=_FEEDBACK_MAX_CHARS,
            placeholder="e.g. I wish it showed the impact of leaving before vesting, or the chart was hard to read...",
            label_visibility="collapsed",
            key=f"feedback_text_{st.session_state.feedback_key}",
        )
        include_details = st.checkbox(
            "Include my calculator inputs and results (helps me understand your feedback)",
            value=False,
            key=f"feedback_details_{st.session_state.feedback_key}",
        )
        if st.form_submit_button("Submit"):
            # [H-3] Abuse controls: enforce a length cap (belt-and-suspenders with
            # the widget's max_chars) and a per-session cooldown so a single client
            # cannot flood the shared Google Sheet and exhaust its write quota.
            elapsed = time.monotonic() - st.session_state.feedback_last_submit
            cleaned = feedback_text.strip()[:_FEEDBACK_MAX_CHARS]
            if not cleaned:
                st.warning("Please enter some feedback before submitting.")
            elif elapsed < _FEEDBACK_COOLDOWN_SECONDS:
                wait = int(_FEEDBACK_COOLDOWN_SECONDS - elapsed) + 1
                st.warning(f"Thanks! Please wait {wait}s before submitting again.")
            else:
                (
                    ip, country, region, city, zip_code, lat, lon,
                    # Not "timezone": that name would shadow datetime.timezone,
                    # which the timestamp below needs (it used to crash here).
                    visitor_tz, isp, is_vpn, is_mobile_net,
                    lang, referrer, platform_hdr, mobile_hdr,
                    browser, browser_ver, os_name, os_ver, device,
                ) = _client_metadata()
                # Calculator details are stored only when the visitor opts in;
                # otherwise those columns stay blank.
                details = [
                    inputs["starting_wage"], inputs["work_years"], inputs["retirement_years"],
                    round(res["cola_pct"], 2),
                    round(res["index_return_pct"], 2),
                    round(inputs["pension_contribution_rate"] * 100, 2),
                    round(inputs["starting_allowance"], 2),
                    round(res["pension_contribution_total"], 2),
                    round(res["pension_redeemed_total"], 2),
                    round(res["personal_fund_values"][inputs["work_years"]], 2),
                    round(res["personal_balance"], 2),
                    # JSON (and so the Sheets API) has no infinity.
                    "over cap" if math.isinf(res["breakeven_rate"]) else round(res["breakeven_rate"], 2),
                    res["years_covered"],
                    "Option A" if simulation.ran_short(res["personal_balance"]) else "Option B",
                ]
                swing_details = [
                    round(st.session_state.get("mc_std", 15.0), 1),
                    round(get_monte_carlo(inputs, st.session_state.get("mc_std", 15.0))["depletion_prob"] * 100, 1),
                ]
                if not include_details:
                    details = [""] * len(details)
                    swing_details = [""] * len(swing_details)
                err = _append_feedback([
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    cleaned,
                    *details,
                    ip, country, region, city, zip_code, lat, lon,
                    visitor_tz, isp, is_vpn, is_mobile_net,
                    lang, referrer, platform_hdr, mobile_hdr,
                    browser, browser_ver, os_name, os_ver, device,
                    page_name,
                    *swing_details,
                ])
                if err:
                    st.warning("Sorry, we couldn't save your feedback right now. Please try again later.")
                else:
                    st.session_state.feedback_last_submit = time.monotonic()
                    st.session_state.feedback_key += 1
                    st.session_state.feedback_success = True
                    st.rerun()

    if st.session_state.feedback_success:
        render_html(
            """
            <div style="background:#d4edda;border:1px solid #c3e6cb;color:#155724;
                        padding:.75rem 1.25rem;border-radius:.375rem;margin:.25rem 0;
                        animation:fb_fade .8s ease-in 2.2s forwards">
                ✓ &nbsp;Thank you. Your feedback is noted.
            </div>
            <style>@keyframes fb_fade{from{opacity:1}to{opacity:0}}</style>
            """
        )
        st.session_state.feedback_success = False
