"""Shared infrastructure for the multipage app.

Holds everything both pages need: Google Sheets plumbing, client metadata,
the sidebar inputs, cached simulation wrappers, the fund chart builder, and
the feedback form. Page-specific copy and layout live in the view modules.

Per-user data is passed between the entry script and the views via
``st.session_state`` (keys ``_inputs`` and ``_results``), never via module
globals, which are process-wide and would leak between sessions.
"""

import ipaddress
import json
import logging
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import gspread
import pandas as pd
import streamlit as st
from plotly import graph_objects as go
from user_agents import parse as _parse_ua

import simulation

_logger = logging.getLogger(__name__)

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


# The math lives in simulation.py with no Streamlit dependency,
# so it is unit-testable; caching is applied here at the app boundary.
run_simulation = st.cache_data(simulation.run_simulation)
compute_breakeven_rate = st.cache_data(simulation.compute_breakeven_rate)
run_monte_carlo = st.cache_data(simulation.run_monte_carlo)
compute_fas = simulation.compute_fas


def render_html(html: str):
    """
    Every ``unsafe_allow_html`` render routes through here. Only ever
    interpolate computed numbers into these strings, never user-supplied text.
    """
    st.markdown(html, unsafe_allow_html=True)


# One-click scenarios for the case studies. Keys/types must match the sidebar
# widgets exactly (int widgets need ints, float widgets floats).
PRESETS = {
    "alice": {
        "label": "Alice: personal fund wins",
        "values": {
            "in_wage": 120000, "in_work_years": 30, "in_retirement_age": 55,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "10, 20",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_allowance_mode": "Enter manually", "allowance_manual": 70458,
            "in_retirement_years": 30, "in_returns": 7.0,
        },
    },
    "bob": {
        "label": "Bob: pension wins",
        "values": {
            "in_wage": 65000, "in_work_years": 20, "in_retirement_age": 55,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_allowance_mode": "Enter manually", "allowance_manual": 27000,
            "in_retirement_years": 40, "in_returns": 5.0,
        },
    },
    "carol": {
        "label": "Carol: personal fund wins",
        "values": {
            "in_wage": 80000, "in_work_years": 35, "in_retirement_age": 60,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "15",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_allowance_mode": "Enter manually", "allowance_manual": 55000,
            "in_retirement_years": 25, "in_returns": 6.0,
        },
    },
    "dave": {
        "label": "Dave: pension wins",
        "values": {
            "in_wage": 95000, "in_work_years": 15, "in_retirement_age": 50,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "",
            "in_promo_pct": 8.0, "in_contrib": 10.0,
            "in_allowance_mode": "Enter manually", "allowance_manual": 42000,
            "in_retirement_years": 35, "in_returns": 4.0,
        },
    },
    "frank": {
        "label": "Frank: personal fund wins",
        "values": {
            "in_wage": 150000, "in_work_years": 25, "in_retirement_age": 55,
            "in_cola": 3.0, "in_step": 5.5, "in_promo_years": "10, 18",
            "in_promo_pct": 10.0, "in_contrib": 10.0,
            "in_allowance_mode": "Enter manually", "allowance_manual": 85000,
            "in_retirement_years": 25, "in_returns": 8.0,
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
- **COLA**: Applied to salary at the end of each working year, taking effect the following year. In retirement, applied to the pension allowance at the end of each year, taking effect the following year.
- **Step increases**: The Step 1 → Step 2 raise occurs 6 months after hire. Since the calculator uses annual periods, Year 1 contributions are averaged over 6 months at Step 1 and 6 months at Step 2. The Steps 2 → 3, 3 → 4, and 4 → 5 raises each take effect at the start of Years 3, 4, and 5 respectively.
- **Promotions**: Applied at the end of the year you specify, taking effect the following year.
""")

        st.subheader("Career")
        starting_wage = st.number_input(
            "Starting Annual Wage ($)",
            value=50000, min_value=0, step=2500,
            key="in_wage",
            help="Your initial salary for the first year you were hired."
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
            help="Your age on the day you expect to retire."
        )
        cola_increase = st.number_input(
            "Cost of Living Adjustment (%)",
            value=3.0, min_value=0.0, max_value=5.5, step=0.1,
            key="in_cola",
            help="Annual salary adjustment announced each October, typically between 2-3.5%. Set to 0 for plans with no COLA. In retirement, your pension check grows by this same percentage each year."
        ) / 100 + 1
        step_increase = st.number_input(
            "Step Increase (%)",
            value=5.5, min_value=0., step=0.1,
            key="in_step",
            help="Annual raise from step progression. Applies in each of your first 4 years."
        ) / 100 + 1
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
            value=8.0, step=1.,
            key="in_promo_pct",
            help="Expected salary bump each time you are promoted."
        ) / 100 + 1

        st.subheader("Pension")
        pension_contribution_rate = st.number_input(
            "Pension Contribution Rate (%)",
            value=10.0, step=1.,
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

        if not manual_override:
            # Auto-determine retirement factor from age and years of service
            _age = int(retirement_age)
            _yrs = int(work_years)
            if _age >= 63 and _yrs >= 30:
                _factor = 0.021
                _is_reduced = False
            elif _age >= 60 and _yrs >= 30:
                _factor = 0.020
                _is_reduced = False
            elif _age >= 55 and _yrs >= 30:
                _factor = 0.020
                _is_reduced = False
            elif _yrs >= 30:
                _factor = 0.020
                _is_reduced = True
            elif _age >= 63 and _yrs >= 5:
                _factor = 0.020
                _is_reduced = False
            else:
                _factor = 0.015
                _is_reduced = False

            if _is_reduced:
                _early_red = st.number_input(
                    "Early Retirement Reduction (%)",
                    value=0.0, min_value=0.0, max_value=50.0, step=0.5,
                    key="in_early_red",
                    help="Your age and years of service qualify for retirement with an early reduction. Enter the exact percentage from your plan's retirement estimator.",
                )
            else:
                _early_red = 0.0

            _fas = compute_fas(starting_wage, int(work_years), cola_increase, step_increase,
                               promotion_years, promotion_increase)
            _reduction = 1.0 - _early_red / 100.0
            _computed_allowance = work_years * _fas * _factor * _reduction

            st.number_input(
                "First-year annual pension allowance ($)",
                value=round(_computed_allowance),
                min_value=0,
                step=500,
                disabled=True,
                key="allowance_formula",
                help=(
                    "Years of Service × Final Average Salary (highest 36 consecutive months) "
                    "× Retirement Factor × Early Retirement Reduction Factor. "
                    "Derived from your career inputs above. Switch to 'Enter manually' to override."
                ),
            )
            starting_allowance = _computed_allowance
        else:
            manual_allowance = st.number_input(
                "First-year annual pension allowance ($)",
                value=70000,
                min_value=0,
                step=2500,
                key="allowance_manual",
                help="Your annual pension payment in the first year of retirement. Find this from your plan's retirement estimator. COLA will compound on top of this each subsequent year.",
            )
            starting_allowance = manual_allowance

        st.subheader("Retirement")
        retirement_years = st.number_input(
            "Years in Retirement Before Death",
            value=30, min_value=1, max_value=60, step=1,
            key="in_retirement_years",
            help="How many years you expect to spend in retirement before you die."
        )
        index_returns_rate = (
            st.number_input(
                "Average Index Returns Rate (%)",
                value=10.0,
                min_value=0.0,
                max_value=25.0,
                step=0.5,
                key="in_returns",
                help=(
                    "Expected annual return on Option B's investment account (not inflation-adjusted). "
                    "⚠ This number matters more than any other input: a 1% change can flip the winner."
                ),
            )
            / 100
            + 1
        )

    return {
        "starting_wage": starting_wage,
        "work_years": int(work_years),
        "retirement_age": int(retirement_age),
        "cola_increase": cola_increase,
        "step_increase": step_increase,
        "promotion_years": promotion_years,
        "promotion_increase": promotion_increase,
        "pension_contribution_rate": pension_contribution_rate,
        "starting_allowance": starting_allowance,
        "retirement_years": int(retirement_years),
        "index_returns_rate": index_returns_rate,
    }


def compute_results(inputs):
    """Run the flat-rate simulation and derive everything both pages display."""
    result = run_simulation(
        inputs["starting_wage"], inputs["work_years"], inputs["cola_increase"],
        inputs["step_increase"], inputs["promotion_years"], inputs["promotion_increase"],
        inputs["pension_contribution_rate"], inputs["starting_allowance"],
        inputs["retirement_years"], inputs["index_returns_rate"],
    )

    personal_fund_values = result["personal_fund_values"]

    # First retirement year where the personal fund is depleted
    depletion_year = next(
        (k for k in range(1, inputs["retirement_years"] + 1)
         if personal_fund_values[inputs["work_years"] + k] <= 0),
        None,
    )

    breakeven_rate = compute_breakeven_rate(
        inputs["starting_wage"], inputs["work_years"], inputs["cola_increase"],
        inputs["step_increase"], inputs["promotion_years"], inputs["promotion_increase"],
        inputs["pension_contribution_rate"], inputs["starting_allowance"],
        inputs["retirement_years"],
    )

    years_covered = inputs["retirement_years"] if depletion_year is None else depletion_year - 1

    return {
        **result,
        "depletion_year": depletion_year,
        "breakeven_rate": breakeven_rate,
        "years_covered": years_covered,
        # Display-only percentages
        "index_return_pct": (inputs["index_returns_rate"] - 1) * 100,
        "cola_pct": (inputs["cola_increase"] - 1) * 100,
        "step_pct": (inputs["step_increase"] - 1) * 100,
        "promotion_pct": (inputs["promotion_increase"] - 1) * 100,
    }


def get_monte_carlo(inputs, std_pct, n_simulations=1000):
    """Cached Monte Carlo run for the current inputs at the given volatility (%)."""
    return run_monte_carlo(
        inputs["starting_wage"], inputs["work_years"], inputs["cola_increase"],
        inputs["step_increase"], inputs["promotion_years"], inputs["promotion_increase"],
        inputs["pension_contribution_rate"], inputs["starting_allowance"],
        inputs["retirement_years"],
        mean_return=inputs["index_returns_rate"] - 1,
        std_return=std_pct / 100.0,
        n_simulations=n_simulations,
    )


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

    _xf = list(years)
    _xr = list(years)[::-1]

    if mc_pcts is not None:
        fig.add_trace(go.Scatter(
            x=_xf + _xr,
            y=list(mc_pcts[0]) + list(mc_pcts[1])[::-1],
            fill="toself", fillcolor="rgba(220,38,38,0.18)",
            line=dict(color="rgba(0,0,0,0)"),
            name="You get unlucky (worst 20% of outcomes)", hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=_xf + _xr,
            y=list(mc_pcts[1]) + list(mc_pcts[2])[::-1],
            fill="toself", fillcolor="rgba(59,130,246,0.18)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Most likely (middle 50% of outcomes)", hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=_xf + _xr,
            y=list(mc_pcts[2]) + list(mc_pcts[3])[::-1],
            fill="toself", fillcolor="rgba(22,163,74,0.18)",
            line=dict(color="rgba(0,0,0,0)"),
            name="You get lucky (best 20% of outcomes)", hoverinfo="skip",
        ))

    # Hover arrays
    _deposits = [0.0] + yearly_data["Pension Contribution"].tolist()
    _withdrawals = [0.0] + yearly_data["Pension Redeemed"].tolist()
    _returns = [0.0] + yearly_data["Market Returns"].tolist()
    _personal_customdata = list(zip(_deposits, _withdrawals, _returns))

    fig.add_trace(go.Scatter(
        x=years,
        y=pension_fund_values,
        mode="lines+markers",
        name="Annual payout amount (same for both options)",
        line=dict(color="#A855F7", width=2),
        marker=dict(color="#A855F7", size=5, symbol="circle"),
        customdata=_withdrawals,
        hovertemplate=(
            "<b>Year %{x}</b><br>"
            "This year paid out: $%{customdata:,.0f}<br>"
            "Running total paid out: $%{y:,.0f}"
            "<extra></extra>"
        ),
        visible=show_ref_line,
    ))

    fig.add_trace(go.Scatter(
        x=years,
        y=personal_fund_values,
        mode="lines+markers",
        name=f"Option B: personal fund balance (fixed {index_return_pct:.1f}% return from sidebar)",
        line=dict(color="#0D9488", width=3),
        customdata=_personal_customdata,
        hovertemplate=(
            "<b>Year %{x}</b><br>"
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
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            x=0.5, xanchor="center",
            font=dict(size=16, color="#1e293b"),
        ),
        xaxis_title="Year (W = Working, R = Retirement)",
        yaxis_title="Dollar Amount ($)",
        xaxis=dict(
            tickangle=45,
            tickmode="array",
            tickvals=[years[i] for i in range(0, len(years), x_tick_step)],
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
        x0=-0.5, x1=work_years + 0.5,
        fillcolor="rgba(0,0,0,0)", layer="below", line_width=0,
        annotation_text="<b>Working Years</b>", annotation_position="top left",
        annotation=dict(
            font_size=13, font_color="#1E3A5F",
            bgcolor="rgba(255,255,255,0.75)", borderpad=5,
        ),
    )
    fig.add_vrect(
        x0=work_years + 0.5, x1=len(years) - 0.5,
        fillcolor="rgba(0,0,0,0)", layer="below", line_width=0,
        annotation_text="<b>Retirement Years</b>", annotation_position="top left",
        annotation=dict(
            font_size=13, font_color="#7C2D12",
            bgcolor="rgba(255,255,255,0.75)", borderpad=5,
        ),
    )
    fig.add_vline(x=work_years, line_width=2, line_dash="dash", line_color="#DC2626")
    _fund_depletes = min(personal_fund_values) < 0
    fig.add_hline(y=0, line_width=2, line_color="#666666",
                  annotation_text="$0 = personal fund depleted" if _fund_depletes else "$0",
                  annotation_position="bottom right")

    if verdict_annotation:
        if _fund_depletes:
            _dep_idx = next(i for i, v in enumerate(personal_fund_values) if v < 0)
            fig.add_annotation(
                x=years[_dep_idx], y=0,
                text=f"<b>✗ Runs out here: {len(years) - 1 - _dep_idx} years of retirement left with no money</b>",
                showarrow=True, arrowhead=2, arrowcolor="#DC2626",
                ax=-40, ay=-60,
                font=dict(size=13, color="#DC2626"),
                bgcolor="rgba(255,255,255,0.85)", borderpad=4,
            )
        else:
            fig.add_annotation(
                x=years[-1], y=personal_fund_values[-1],
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

    money_cols = [c for c in table.columns if c != "Year"]

    # These sets don't depend on `col`; compute once, not per column.
    renamed_running = {rename_map.get(k, k) for k in (
        "Pension Contribution Total", "Pension Redeemed Total")}
    renamed_balance = {rename_map.get(k, k) for k in ("Balance",)}
    total_row = {"Year": "Total"}
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
    res = st.session_state["_results"]

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
                    round(res["breakeven_rate"], 2),
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
