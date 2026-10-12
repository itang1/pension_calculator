"""Shared infrastructure for the multipage app.

Holds everything both pages need: Google Sheets plumbing, client metadata,
the sidebar inputs, cached simulation wrappers, the fund chart builder, and
the feedback form. Page-specific copy and layout live in the view modules.

Per-user data is passed between the entry script and the views via
``st.session_state`` (keys ``_inputs``, ``_results`` for display, and
``_results_nominal`` in future dollars), never via module
globals, which are process-wide and would leak between sessions.
"""

import ipaddress
import json
import logging
import math
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


def _append_feedback(row: list):
    """Append a feedback row. Returns ``None`` on success, else ``True``.

    [H-2] The raw exception is logged server-side only. gspread errors can
    contain the spreadsheet ID, service-account email, and API payloads, so we
    never surface the exception text to end users.
    """
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
run_simulation = st.cache_data(simulation.run_simulation)
compute_breakeven_rate = st.cache_data(simulation.compute_breakeven_rate)
run_monte_carlo = st.cache_data(simulation.run_monte_carlo)
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
        "label": "Alice: personal fund wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 120000, "in_work_years": 30, "in_retirement_age": 55,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "10, 20",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 30, "in_returns": 10.0,
        },
    },
    "bob": {
        "label": "Bob: pension wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 65000, "in_work_years": 20, "in_retirement_age": 60,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 35, "in_returns": 5.0,
        },
    },
    "carol": {
        "label": "Carol: personal fund wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 80000, "in_work_years": 35, "in_retirement_age": 60,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "15",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 25, "in_returns": 9.0,
        },
    },
    "dave": {
        "label": "Dave: pension wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 95000, "in_work_years": 15, "in_retirement_age": 63,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 25, "in_returns": 4.0,
        },
    },
    "frank": {
        "label": "Frank: personal fund wins",
        "values": {
            "in_hire_year": CURRENT_YEAR, "in_wage_mode": "My starting wage",
            "in_wage": 150000, "in_work_years": 25, "in_retirement_age": 60,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "10, 18",
            "in_promo_pct": 10.0, "in_contrib": 10.0,
            "in_step_count": 4, "in_step_midyear": True,
            "in_allowance_mode": "Estimate for me", "in_inflation": 2.5,
            "in_retirement_years": 25, "in_returns": 10.0,
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
    preset_id = st.session_state.pop("_pending_preset", None)
    if preset_id:
        preset = PRESETS[preset_id]
        for k, v in preset["values"].items():
            st.session_state[k] = v
        st.toast(f"Loaded the scenario: {preset['label']}. The whole page now shows these numbers.", icon="✅")


def render_sidebar():
    """Render all shared inputs in the sidebar and return them as a dict.

    Called from the entry script on every rerun (i.e. on every page), so the
    widgets keep their state across page switches without any session_state
    pinning.
    """
    with st.sidebar:
        st.header("Input Assumptions")

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
                "Your Annual Wage Today ($)",
                value=120000, min_value=0, step=2500,
                key="in_current_wage",
                help=f"What you are paid now, in {CURRENT_YEAR}.",
            )
        else:
            starting_wage = st.number_input(
                "Starting Annual Wage ($)",
                value=120000, min_value=0, step=2500,
                key="in_wage",
                help=f"Your salary in your first year on the job, in {hire_year} dollars (what you were actually paid then).",
            )
        work_years = st.number_input(
            "Years to Work",
            value=30, min_value=1, step=1,
            key="in_work_years",
            help="How many years you plan to work before retirement."
        )
        retirement_age = st.number_input(
            "Age at Retirement",
            value=55, min_value=18, max_value=75, step=1,
            key="in_retirement_age",
            help="Your age on the day you expect to retire. Your age when hired is this minus Years to Work."
        )
        hire_age = int(retirement_age) - int(work_years)
        if hire_age < 16:
            st.error(
                f"Retiring at {int(retirement_age)} after {int(work_years)} years means starting work at "
                f"age {hire_age}. Raise your retirement age or lower your years of work to continue."
            )
            st.stop()
        st.caption(
            f"You are hired at age {hire_age} (in {hire_year}) and retire at {int(retirement_age)} "
            f"(in {hire_year + int(work_years)})."
        )
        cola_increase = st.number_input(
            "Cost of Living Adjustment (%)",
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
        promotion_years_input = st.text_input(
            "Promotion Years",
            value="10, 20",
            key="in_promo_years",
            help="Comma-separated year numbers within your career when you expect a promotion (e.g. 10, 20). Leave blank if none."
        )
        # Parse promotion years exactly once.
        _promo_tokens = [t.strip() for t in promotion_years_input.split(",") if t.strip()]
        _promo_bad = [t for t in _promo_tokens if not t.isdigit()]
        promotion_years = tuple(int(t) for t in _promo_tokens if t.isdigit())
        _promo_oob = [y for y in promotion_years if y < 1 or y > int(work_years)]
        if _promo_bad:
            st.error(f"Can't parse promotion year(s): {', '.join(_promo_bad)}. Enter whole numbers only, then results will update.")
            st.stop()
        if _promo_oob:
            st.error(f"Promotion year(s) {', '.join(str(y) for y in _promo_oob)} fall outside your {int(work_years)}-year career. Fix or remove them to continue.")
            st.stop()
        promotion_increase = st.number_input(
            "Promotion Increase (%)",
            value=8.0, min_value=0.0, max_value=100.0, step=1.,
            key="in_promo_pct",
            help="Expected salary bump each time you are promoted."
        ) / 100 + 1

        if _wage_mode == "My wage today":
            # This calendar year is career year (years_so_far + 1). Undo every
            # raise up to it (COLA, steps, promotions) to recover the starting wage.
            _year_now = years_so_far + 1
            if _year_now > int(work_years):
                st.error(
                    f"Hired in {hire_year}, you would have finished your {int(work_years)}-year career "
                    f"already. Raise Years to Work, or enter your starting wage instead."
                )
                st.stop()
            _growth = simulation.salary_schedule(
                1.0, _year_now, cola_increase, step_increase, promotion_years,
                promotion_increase, int(step_count), first_step_midyear)[-1]
            starting_wage = current_wage / _growth
            st.caption(
                f"That works out to a starting wage of about ${starting_wage:,.0f} in {hire_year}, "
                f"using the raises you entered above."
            )

        st.subheader("Pension")
        pension_contribution_rate = st.number_input(
            "Pension Contribution Rate (%)",
            value=10.0, min_value=0.0, max_value=100.0, step=1.,
            key="in_contrib",
            help="Percentage of your salary automatically deducted and contributed to the pension system each year."
        ) / 100

        st.markdown("**Starting Pension Allowance**")

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

        plan = None
        if not manual_override:
            _fas = compute_fas(starting_wage, int(work_years), cola_increase, step_increase,
                               promotion_years, promotion_increase,
                               int(step_count), first_step_midyear)
            plan = simulation.plan_benefit(int(work_years), int(retirement_age), _fas)
            starting_allowance = plan["allowance"]

            # The value is pushed through session_state (not ``value=``) so a
            # keyed, disabled widget always shows the freshly computed figure.
            st.session_state["allowance_formula"] = round(starting_allowance)
            st.number_input(
                "First-year annual pension allowance ($)",
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
            if plan["status"] == "unvested":
                _refund = simulation.refund_with_interest(
                    [s * pension_contribution_rate for s in simulation.salary_schedule(
                        starting_wage, int(work_years), cola_increase, step_increase,
                        promotion_years, promotion_increase, int(step_count), first_step_midyear)])
                st.warning(
                    f"With {int(work_years)} years of service you would not vest, so there is no "
                    f"lifetime allowance. Instead your contributions are refunded with "
                    f"{simulation.PLAN_REFUND_INTEREST_PCT:g}% interest (about ${_refund:,.0f}). "
                    f"In that case Option B only wins if it earns more than "
                    f"{simulation.PLAN_REFUND_INTEREST_PCT:g}% a year."
                )
            else:
                _rule = f"{plan['factor_pct']:g}% per year of service"
                if plan["reduction"] < 1:
                    _rule += f", reduced to {plan['reduction'] * 100:.1f}% for retiring before 55"
                if plan["capped"]:
                    _rule += ", capped at 80% of your final average salary"
                _today = starting_allowance / inflation ** (
                    int(work_years) + plan["deferral_years"] - years_so_far)
                st.caption(f"{_rule}. That is about ${_today:,.0f} a year in {CURRENT_YEAR} dollars.")
                if plan["status"] == "deferred":
                    st.warning(
                        f"Without 30 years of service you can't start a pension before age "
                        f"{simulation.PLAN_FULL_AGE}. Leaving at {int(retirement_age)} gives a deferred pension "
                        f"from age {simulation.PLAN_FULL_AGE} with no COLA, so neither option pays anything for "
                        f"your first {plan['deferral_years']} years of retirement."
                    )
        else:
            manual_allowance = st.number_input(
                "First-year annual pension allowance ($)",
                value=70000,
                min_value=0,
                step=2500,
                key="allowance_manual",
                help="Your annual pension payment in the first year of retirement. Find this from your plan's retirement estimator. COLA will compound on top of this each subsequent year.",
            )
            _basis = st.radio(
                "This amount is in",
                ["Today's dollars", "Dollars at retirement"],
                format_func=lambda o: f"{CURRENT_YEAR} dollars" if o == "Today's dollars" else o,
                key="in_allowance_basis",
                help=(
                    "Plan estimators usually show your benefit in today's dollars. The calculator "
                    "grows your salary in future dollars, so a today's-dollars figure is first "
                    "grown by inflation to your retirement year. Mixing the two would make the "
                    "pension look several times smaller than it is."
                ),
            )
            if _basis == "Today's dollars":
                starting_allowance = simulation.to_retirement_dollars(
                    manual_allowance, int(work_years) - years_so_far, inflation)
                st.caption(
                    f"That is about ${starting_allowance:,.0f} in {hire_year + int(work_years)}, "
                    f"your first year of retirement."
                )
            else:
                starting_allowance = manual_allowance

        st.subheader("Retirement")
        retirement_years = st.number_input(
            "Years in Retirement Before Death",
            value=30, min_value=1, max_value=60, step=1,
            key="in_retirement_years",
            help="How many years you expect to spend in retirement before you die."
        )
        st.caption(f"Retirement runs from age {int(retirement_age)} to {int(retirement_age) + int(retirement_years)}.")
        inflation_pct = st.number_input(
            "Expected Inflation (%)",
            value=2.5, min_value=0.0, max_value=10.0, step=0.1,
            key="in_inflation",
            help=(
                "Average yearly rise in prices (CPI). The pension's COLA in retirement follows "
                f"inflation up to {simulation.PLAN_RETIREE_COLA_CAP_PCT:g}% a year, so higher inflation "
                f"slowly erodes it. Also used to show amounts in {CURRENT_YEAR} dollars."
            ),
        )
        index_returns_rate = (
            st.number_input(
                "Average Index Returns Rate (%)",
                value=7.0,
                min_value=0.0,
                max_value=25.0,
                step=0.5,
                key="in_returns",
                help=(
                    "Expected annual return on Option B's investment account (not inflation-adjusted), "
                    "as a compound rate: the growth you would get if every year returned the same. "
                    "⚠ This number matters more than any other input: a 1% change can flip the winner."
                ),
            )
            / 100
            + 1
        )

    retiree_cola_pct = min(inflation_pct, simulation.PLAN_RETIREE_COLA_CAP_PCT)
    if plan is not None and not plan["cola_applies"]:
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
        "deferral_years": 0 if plan is None else plan["deferral_years"],
        "plan_status": "manual" if plan is None else plan["status"],
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

    # First retirement year where the personal fund is depleted
    depletion_year = next(
        (k for k in range(1, inputs["retirement_years"] + 1)
         if personal_fund_values[inputs["work_years"] + k] <= 0),
        None,
    )

    breakeven_rate = compute_breakeven_rate(*_engine_args(inputs), **_engine_kwargs(inputs))

    years_covered = inputs["retirement_years"] if depletion_year is None else depletion_year - 1

    return {
        **result,
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
    for col in ("Salary", "Start Balance", "Pension Contribution", "Pension Redeemed",
                "Market Returns", "Balance"):
        df[col] = df[col].to_numpy() / d
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
    out["real_dollars"] = True
    return out


def deflate_mc(mc, inputs):
    """Monte Carlo outputs in this year's dollars (same deflators as the flat path)."""
    d = _deflators(inputs, mc["percentiles"].shape[1])
    out = dict(mc)
    out["percentiles"] = mc["percentiles"] / d
    out["median_path"] = mc["median_path"] / d
    out["final_balances"] = mc["final_balances"] / d[-1]
    return out


def dollars_note(res):
    """Suffix for chart titles saying which dollars are shown."""
    return f" (in {CURRENT_YEAR} dollars)" if res.get("real_dollars") else ""


# --- Shareable links ----------------------------------------------------------------
# Every sidebar input (plus the display toggle and the swing slider) is mirrored
# into the page URL, so a copied link reopens the same scenario. Values are
# parsed and range-checked here before they touch widget state.
_SHARE_SPEC = {
    "in_hire_year": (int, CURRENT_YEAR - 60, CURRENT_YEAR),
    "in_wage_mode": (["My starting wage", "My wage today"], None, None),
    "in_current_wage": (int, 0, 10_000_000),
    "in_wage": (int, 0, 10_000_000),
    "in_work_years": (int, 1, 60),
    "in_retirement_age": (int, 18, 75),
    "in_cola": (float, 0.0, 5.5),
    "in_step": (float, 0.0, 50.0),
    "in_step_count": (int, 0, 20),
    "in_step_midyear": (bool, None, None),
    "in_promo_years": (str, None, None),
    "in_promo_pct": (float, 0.0, 100.0),
    "in_contrib": (float, 0.0, 100.0),
    "in_allowance_mode": (["Estimate for me", "Enter manually"], None, None),
    "allowance_manual": (int, 0, 10_000_000),
    "in_allowance_basis": (["Today's dollars", "Dollars at retirement"], None, None),
    "in_retirement_years": (int, 1, 60),
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
        value = kind(float(raw)) if kind is int else kind(raw)
    except ValueError:
        return None
    if not math.isfinite(value) or value < lo or value > hi:
        return None
    return value


def apply_query_params():
    """Load inputs from the URL once per session, before any widget renders."""
    if st.session_state.get("_qp_applied"):
        return
    st.session_state["_qp_applied"] = True
    for key, spec in _SHARE_SPEC.items():
        raw = st.query_params.get(_param_name(key))
        if raw is None:
            continue
        value = _parse_param(raw, spec)
        if value is not None:
            st.session_state[key] = value


def sync_query_params():
    """Mirror the current inputs into the URL so the address bar is shareable."""
    params = {_param_name(k): str(st.session_state[k])
              for k in _SHARE_SPEC if k in st.session_state}
    if dict(st.query_params) != params:
        st.query_params.from_dict(params)


def build_rate_curve_chart(inputs, res):
    """Money left at death for Option B across flat return rates.

    One line: above $0 Option B wins, below it the pension wins. The user's
    assumed rate and the break-even rate are marked so the single break-even
    number becomes something you can see.
    """
    rates = [r / 2 for r in range(0, 31)]  # 0% to 15% in half-point steps
    real = res.get("real_dollars", False)
    finals = []
    for r in rates:
        sim = run_simulation(*_engine_args(inputs), 1 + r / 100, **_engine_kwargs(inputs))
        final = sim["personal_balance"]
        if real:
            final /= inputs["inflation"] ** _years_after_now(
                inputs, inputs["work_years"] + inputs["retirement_years"])
        finals.append(final)
    ink, muted = "#1e293b", "#64748B"

    fig = go.Figure(go.Scatter(
        x=rates, y=finals, mode="lines",
        line=dict(color="#0D9488", width=2),
        hovertemplate="Flat return %{x:.1f}%<br>Option B at death: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_width=1.5, line_color=muted)
    yr = max(abs(min(finals)), abs(max(finals)))
    fig.add_annotation(x=rates[1], y=yr * 0.9, text="Option B wins here (money left over)",
                       showarrow=False, xanchor="left", font=dict(size=12, color=muted))
    fig.add_annotation(x=rates[-2], y=-yr * 0.9, text="The pension wins here (Option B runs out)",
                       showarrow=False, xanchor="right", font=dict(size=12, color=muted))

    current = res["index_return_pct"]
    fig.add_vline(x=current, line_width=1.5, line_dash="dash", line_color=ink,
                  annotation_text=f"Your assumption: {current:.1f}%",
                  annotation_position="top", annotation_font_color=ink)
    be = res["breakeven_rate"]
    if 0 < be <= rates[-1]:
        fig.add_trace(go.Scatter(
            x=[be], y=[0], mode="markers",
            marker=dict(size=10, color="#0D9488", line=dict(width=2, color="white")),
            hovertemplate=f"Break-even: {be:.1f}%<extra></extra>",
        ))
        fig.add_annotation(x=be, y=0, text=f"Break-even {be:.1f}%", showarrow=True,
                           arrowhead=0, ax=40, ay=40, font=dict(size=12, color=ink),
                           bgcolor="rgba(255,255,255,0.85)")

    fig.update_layout(
        title=dict(text=f"<b>Option B's money left at death, by flat return rate{dollars_note(res)}</b>",
                   x=0.5, xanchor="center", font=dict(size=15, color=ink)),
        xaxis=dict(title="Flat annual return (%)", ticksuffix="%", showgrid=False, range=[0, rates[-1]]),
        yaxis=dict(title="Money left at death ($)", tickformat=",", gridcolor="#eef0f2",
                   range=[-yr * 1.1, yr * 1.1]),
        plot_bgcolor="white", showlegend=False, hovermode="x",
        margin=dict(l=40, r=20, t=60, b=50),
    )
    return fig


def build_fund_chart(inputs, res, show_ref_line, mc_pcts=None, title=None,
                     verdict_annotation=False):
    """Build the fund-over-time chart, optionally with Monte Carlo bands.

    With ``verdict_annotation=True`` the chart states its own conclusion at
    the spot where it happens (money left over at the end, or the year the
    fund runs dry), so a reader who never touches the legend still gets the
    answer.
    """
    years = res["years"]
    personal_fund_values = res["personal_fund_values"]
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
    all_values = [v for v in personal_fund_values if v is not None]
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
            name="Unluckiest futures", hoverinfo="skip",
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
            name="Luckiest futures", hoverinfo="skip",
        ))

    # Hover arrays
    _deposits = [0.0] + yearly_data["Pension Contribution"].tolist()
    _withdrawals = [0.0] + yearly_data["Pension Redeemed"].tolist()
    _returns = [0.0] + yearly_data["Market Returns"].tolist()
    _cal = calendar_years_for(inputs)
    _personal_customdata = list(zip(_deposits, _withdrawals, _returns, years, _cal))

    fig.add_trace(go.Scatter(
        x=ages,
        y=pension_fund_values,
        mode="lines+markers",
        name="Annual payout amount (same for both options)",
        line=dict(color="#A855F7", width=2),
        marker=dict(color="#A855F7", size=5, symbol="circle"),
        customdata=list(zip(_withdrawals, years, _cal)),
        hovertemplate=(
            "<b>Age %{x}</b> · %{customdata[2]} (year %{customdata[1]})<br>"
            "This year paid out: $%{customdata[0]:,.0f}<br>"
            "Running total paid out: $%{y:,.0f}"
            "<extra></extra>"
        ),
        visible=show_ref_line,
    ))

    fig.add_trace(go.Scatter(
        x=ages,
        y=personal_fund_values,
        mode="lines+markers",
        name=f"Option B: personal fund balance (fixed {index_return_pct:.1f}% return from sidebar)",
        line=dict(color="#0D9488", width=3),
        customdata=_personal_customdata,
        hovertemplate=(
            "<b>Age %{x}</b> · %{customdata[4]} (year %{customdata[3]})<br>"
            "Deposit this year: $%{customdata[0]:,.0f}<br>"
            "Withdrawal this year: $%{customdata[1]:,.0f}<br>"
            "Market returns this year: $%{customdata[2]:,.0f}<br>"
            "Personal fund balance: $%{y:,.0f}"
            "<extra></extra>"
        ),
    ))

    _y_pad = data_range * 0.12
    if title is None:
        title = f"Option B Personal Fund Balance at a flat {index_return_pct:.1f}% annual return"
    title += dollars_note(res)
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            x=0.5, xanchor="center",
            font=dict(size=16, color="#1e293b"),
        ),
        xaxis_title="Your age",
        yaxis_title="Dollar Amount ($)",
        xaxis=dict(
            tickmode="array",
            tickvals=[ages[i] for i in range(0, len(ages), x_tick_step)],
            tickfont=dict(size=10),
            showgrid=True,
            gridcolor="lightgray",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="lightgray",
            dtick=y_tick_interval,
            tickformat=",",
            separatethousands=True,
            range=[data_min - _y_pad, data_max + _y_pad],
        ),
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
        margin=dict(l=40, r=20, t=50, b=120),
    )

    fig.add_vrect(
        x0=ages[0] - 0.5, x1=ages[work_years] + 0.5,
        fillcolor="rgba(0,0,0,0)", layer="below", line_width=0,
        annotation_text="<b>Working Years</b>", annotation_position="top left",
        annotation=dict(
            font_size=13, font_color="#1E3A5F",
            bgcolor="rgba(255,255,255,0.75)", borderpad=5,
        ),
    )
    fig.add_vrect(
        x0=ages[work_years] + 0.5, x1=ages[-1] + 0.5,
        fillcolor="rgba(0,0,0,0)", layer="below", line_width=0,
        annotation_text="<b>Retirement Years</b>", annotation_position="top left",
        annotation=dict(
            font_size=13, font_color="#7C2D12",
            bgcolor="rgba(255,255,255,0.75)", borderpad=5,
        ),
    )
    fig.add_vline(x=ages[work_years], line_width=2, line_dash="dash", line_color="#DC2626")
    _fund_depletes = min(personal_fund_values) < 0
    fig.add_hline(y=0, line_width=2, line_color="#666666",
                  annotation_text="$0 = personal fund depleted" if _fund_depletes else "$0",
                  annotation_position="bottom right")

    if verdict_annotation:
        if _fund_depletes:
            _dep_idx = next(i for i, v in enumerate(personal_fund_values) if v < 0)
            fig.add_annotation(
                x=ages[_dep_idx], y=0,
                text=f"<b>✗ Runs out by age {ages[_dep_idx]}: {len(years) - 1 - _dep_idx} years of retirement left with no money</b>",
                showarrow=True, arrowhead=2, arrowcolor="#DC2626",
                ax=-40, ay=-60,
                font=dict(size=13, color="#DC2626"),
                bgcolor="rgba(255,255,255,0.85)", borderpad=4,
            )
        else:
            fig.add_annotation(
                x=ages[-1], y=personal_fund_values[-1],
                text=f"<b>✓ ${personal_fund_values[-1]:,.0f} left over, yours to keep</b>",
                showarrow=True, arrowhead=2, arrowcolor="#0D9488",
                ax=-90, ay=-40,
                font=dict(size=13, color="#0D9488"),
                bgcolor="rgba(255,255,255,0.85)", borderpad=4,
            )

    return fig


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
                    timezone, isp, is_vpn, is_mobile_net,
                    lang, referrer, platform_hdr, mobile_hdr,
                    browser, browser_ver, os_name, os_ver, device,
                ) = _client_metadata()
                err = _append_feedback([
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    cleaned,
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
                    "Option A" if res["personal_balance"] <= 0 else "Option B",
                    ip, country, region, city, zip_code, lat, lon,
                    timezone, isp, is_vpn, is_mobile_net,
                    lang, referrer, platform_hdr, mobile_hdr,
                    browser, browser_ver, os_name, os_ver, device,
                    page_name,
                    round(st.session_state.get("mc_std", 15.0), 1),
                    round(get_monte_carlo(inputs, st.session_state.get("mc_std", 15.0))["depletion_prob"] * 100, 1),
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
