import json
import math
import time
import urllib.request
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from plotly import graph_objects as go
import gspread
from user_agents import parse as _parse_ua

_SPREADSHEET_ID = "1-H0MxbLs4QhES0tbXT4EztNm-5y-GY_jOzwJnwprP1M"

_FEEDBACK_HEADERS = [
    "Timestamp", "Feedback",
    "Starting Wage", "Work Years", "Retirement Years",
    "COLA %", "Index Returns %", "Pension Contribution %", "First-Year Allowance",
    "Pension Contributed", "Pension Received", "Fund at Retirement",
    "Final Fund Balance", "Break-even Rate %", "Years Fund Covers", "Winner",
    "IP", "Country", "Region", "City", "Zip", "Lat", "Lon",
    "Timezone", "ISP", "VPN/Proxy", "Mobile Network",
    "Accept-Language", "Referrer", "Platform", "Mobile Browser",
    "Browser", "Browser Version", "OS", "OS Version", "Device",
]


@st.cache_resource
def _get_feedback_sheet():
    return gspread.service_account_from_dict(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    ).open_by_key(_SPREADSHEET_ID).sheet1


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

    if ip not in ("unknown", "127.0.0.1", "::1"):
        try:
            fields = "status,country,regionName,city,zip,lat,lon,timezone,isp,proxy,mobile"
            with urllib.request.urlopen(
                f"http://ip-api.com/json/{ip}?fields={fields}", timeout=3
            ) as r:
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
            pass

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
    try:
        ws = _get_feedback_sheet()
        if ws.acell("A1").value != "Timestamp":
            ws.insert_row(_FEEDBACK_HEADERS, 1)
        ws.append_row(row)
        return None
    except Exception as e:
        return str(e)


_VISIT_HEADERS = [
    "Timestamp",
    "IP", "Country", "Region", "City", "Zip", "Lat", "Lon",
    "Timezone", "ISP", "VPN/Proxy", "Mobile Network",
    "Accept-Language", "Referrer", "Platform", "Mobile Browser",
    "Browser", "Browser Version", "OS", "OS Version", "Device",
]


@st.cache_resource
def _get_visit_sheet():
    ss = gspread.service_account_from_dict(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    ).open_by_key(_SPREADSHEET_ID)
    try:
        return ss.worksheet("Visits")
    except gspread.exceptions.WorksheetNotFound:
        return ss.add_worksheet(title="Visits", rows=5000, cols=len(_VISIT_HEADERS))


def _log_visit():
    try:
        ws = _get_visit_sheet()
        if ws.acell("A1").value != "Timestamp":
            ws.insert_row(_VISIT_HEADERS, 1)
        ws.append_row([datetime.now().isoformat(timespec="seconds"), *_client_metadata()])
    except Exception:
        pass


st.set_page_config(layout="wide")


def render_breakdown_table(df, phase_prefix, rename_map, balance_col=None):
    """Render one side of the year-over-year breakdown."""
    table = df[df["Year"].str.startswith(phase_prefix)].copy()
    table = table.rename(columns=rename_map)

    money_cols = [c for c in table.columns if c != "Year"]

    total_row = {"Year": "Total"}
    for col in money_cols:
        renamed_running = {rename_map.get(k, k) for k in (
            "Pension Contribution Total", "Pension Redeemed Total")}
        renamed_balance = {rename_map.get(k, k) for k in ("Balance",)}
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

    styler = table.style.format("${:,.0f}", subset=money_cols, na_rep="—")
    styler = styler.apply(_bold_total, axis=1)
    if balance_col is not None:
        styler = styler.map(_highlight_negative, subset=[balance_col])
    return styler


@st.cache_data
def run_simulation(starting_wage, work_years, cola_increase, step_increase,
                   promotion_years, promotion_increase, pension_contribution_rate,
                   starting_allowance, retirement_years, index_returns_rate):
    pension_contribution_total = 0
    pension_redeemed_total = 0
    personal_balance = 0
    salary = starting_wage
    pension_redeemed = starting_allowance

    years = ["W0"]
    pension_fund_values = [0]
    personal_fund_values = [0]
    hover_data = [[0, 0, 0, 0, 0]]
    rows = []

    # Work phase
    for work_year in range(1, work_years + 1):
        if work_year == 1:
            effective_salary = salary * (1 + step_increase) / 2
        else:
            effective_salary = salary

        pension_contribution_this_year = effective_salary * pension_contribution_rate
        pension_contribution_total += pension_contribution_this_year

        start_balance = personal_balance
        market_returns = personal_balance * (index_returns_rate - 1)
        personal_balance = personal_balance + market_returns + pension_contribution_this_year

        years.append(f"W{work_year}")
        pension_fund_values.append(0)
        personal_fund_values.append(personal_balance)
        hover_data.append([pension_contribution_this_year, 0, pension_contribution_this_year, 0, market_returns])

        rows.append({
            "Year": f"W{work_year}",
            "Salary": effective_salary,
            "Start Balance": start_balance,
            "Pension Contribution": pension_contribution_this_year,
            "Pension Contribution Total": pension_contribution_total,
            "Pension Redeemed": 0.0,
            "Pension Redeemed Total": 0.0,
            "Market Returns": market_returns,
            "Balance": personal_balance,
        })

        salary *= cola_increase
        if 1 <= work_year < 5:
            salary *= step_increase
        if work_year in promotion_years:
            salary *= promotion_increase

    # Retirement phase
    for ret_year in range(1, retirement_years + 1):
        pension_redeemed_total += pension_redeemed

        start_balance = personal_balance
        market_returns = personal_balance * (index_returns_rate - 1)
        personal_balance = personal_balance - pension_redeemed + market_returns

        years.append(f"R{ret_year}")
        pension_fund_values.append(pension_redeemed_total)
        personal_fund_values.append(personal_balance)
        hover_data.append([0, pension_redeemed, 0, pension_redeemed, market_returns])

        rows.append({
            "Year": f"R{ret_year}",
            "Salary": float("nan"),
            "Start Balance": start_balance,
            "Pension Contribution": 0.0,
            "Pension Contribution Total": 0.0,
            "Pension Redeemed": pension_redeemed,
            "Pension Redeemed Total": pension_redeemed_total,
            "Market Returns": market_returns,
            "Balance": personal_balance,
        })

        pension_redeemed *= cola_increase

    yearly_data = pd.DataFrame(rows)

    return {
        "years": years,
        "pension_fund_values": pension_fund_values,
        "personal_fund_values": personal_fund_values,
        "hover_data": hover_data,
        "yearly_data": yearly_data,
        "pension_contribution_total": pension_contribution_total,
        "pension_redeemed_total": pension_redeemed_total,
        "personal_balance": personal_balance,
    }


def compute_fas(starting_wage, work_years, cola_increase, step_increase,
                promotion_years, promotion_increase):
    sim_sal = starting_wage
    sal_hist = []
    for yr in range(1, work_years + 1):
        eff = sim_sal * (1 + step_increase) / 2 if yr == 1 else sim_sal
        sal_hist.append(eff)
        sim_sal *= cola_increase
        if 1 <= yr < 5:
            sim_sal *= step_increase
        if yr in promotion_years:
            sim_sal *= promotion_increase
    if len(sal_hist) >= 3:
        return max(sum(sal_hist[i:i + 3]) / 3 for i in range(len(sal_hist) - 2))
    return sum(sal_hist) / len(sal_hist) if sal_hist else starting_wage


def compute_breakeven_rate(starting_wage, work_years, cola_increase, step_increase,
                            promotion_years, promotion_increase, pension_contribution_rate,
                            starting_allowance, retirement_years):
    sim_args = (starting_wage, work_years, cola_increase, step_increase,
                promotion_years, promotion_increase, pension_contribution_rate,
                starting_allowance, retirement_years)
    if run_simulation(*sim_args, 1.0)["personal_balance"] > 0:
        return 0.0
    if run_simulation(*sim_args, 1.25)["personal_balance"] <= 0:
        return 25.0
    lo, hi = 0.0, 0.25
    for _ in range(30):
        mid = (lo + hi) / 2
        if run_simulation(*sim_args, 1.0 + mid)["personal_balance"] > 0:
            hi = mid
        else:
            lo = mid
    return hi * 100


def render_result_banner(personal_balance, retirement_years, depletion_year,
                          breakeven_rate, current_rate_pct):
    rate_buffer = current_rate_pct - breakeven_rate
    if personal_balance > 0:
        st.markdown(f"""
<div style="background-color:#CCFBF1; border-left:5px solid #0D9488; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Based on your inputs, Option B (personal fund) comes out ahead.</strong><br><br>
After {int(retirement_years)} years of retirement, Option B would still have <strong>${personal_balance:,.0f}</strong> remaining for you to keep (donate, pass on, etc.), on top of having paid out the same income as Option A every single year. Option A leaves nothing at death (besides potential survivor benefits, if applicable).
<br><br><em>At your {current_rate_pct:.1f}% return assumption, you are {rate_buffer:.1f} percentage points above the {breakeven_rate:.1f}% break-even return rate.</em>
</div>
""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
<div style="background-color:#FEF3C7; border-left:5px solid #D97706; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Based on your inputs, Option A (pension) comes out ahead.</strong><br><br>
Before your {int(retirement_years)}-year retirement was over, Option B would have fully depleted in retirement year {depletion_year}, leaving {int(retirement_years) - depletion_year} years without coverage. The investment returns on Option B cannot sustain that many years of withdrawals, so Option A's lifetime guarantee is the more reliable choice.
<br><br><em>Your fund would need at least a {breakeven_rate:.1f}% annual return (you entered {current_rate_pct:.1f}%) to last the full retirement period.</em>
</div>
""", unsafe_allow_html=True)


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
    _log_visit()

st.title("Is Your Pension Worth It?")

st.markdown("""
Many public employees (such as teachers, law enforcement officers, and civil servants) are required to contribute part of each paycheck to a pension plan (e.g. a flat 10%). In return, the pension pays a guaranteed annual benefit in retirement for life, regardless of market performance.

In this calculator, we ask the question: **Instead of participating in the pension program, if an employee had the alternative option to invest that same money into their own personal retirement account, which option would produce better outcomes for them?**
""")

st.markdown(
    """
<div style="background-color:#F1F5F9; border-left:5px solid #64748B; padding:0.75rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<em>&larr; On the left sidebar, enter your own assumptions about salary, contribution rate, investment return, and retirement timeline to see how the two options compare.</em>
</div>
""",
    unsafe_allow_html=True,
)

st.space("small")

with st.expander("Explanation of the Two Options"):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
<div style="background-color:#FEF3C7; border-left:5px solid #D97706; padding:1rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Option A: Traditional Pension</strong><br><br>
Each year, a fixed percentage of your paycheck (e.g. 10%) is automatically deducted and funneled directly into your organization's pension system. The funds are then managed by professional fund managers who ensure its long-term stability and growth. In return, once you retire, the pension program will pay you a guaranteed annual payment for the rest of your life, regardless of broad market performance. (The specific amount will depend on your salary, years of service, and the pension formula used by your organization.)
</div>
""", unsafe_allow_html=True)
    with col_b:
        st.markdown("""
<div style="background-color:#CCFBF1; border-left:5px solid #0D9488; padding:1rem 1.2rem; border-radius:0.5rem; color:#1e293b;">
<strong>Option B: Personal Retirement Account</strong><br><br>
Instead of contributing to the pension, imagine that you deposit that same amount (e.g. 10%) each year into your own personal investment account. You have total control over how to invest the funds, and the balance will grow with market returns depending on your investment choices. Imagine that in retirement, you choose to withdraw the same annual amount that the pension would have paid. Additionally, any remaining balance in your account at the end of your life is yours to keep or donate as well.
</div>
""", unsafe_allow_html=True)

with st.expander("Limitations & Assumptions of the Tool"):
    st.markdown("""
This calculator is an educational tool, not a comprehensive financial model. The inputs you provide are applied with several simplifying assumptions:

**Constant input rates.** The investment return, COLA, and step increase you enter are treated as fixed values applied every year. Real markets and salary schedules fluctuate, and a few bad return years early in retirement hurt far more than a steady average suggests.

**Equal tax treatment for both options.** The contribution rate is applied to the personal account on the same pre-tax basis as the pension. This is fine if you have room in a 457(b) plan (a tax-advantaged account available to government employees, similar to a 401k), which has its own contribution limit separate from your pension. But if you have no tax-advantaged space available, the personal account is actually disadvantaged in a way that is not factored in here.

**Annual, end-of-period timing.** All contributions, deposits, and withdrawals are modeled as single lump sums at the end of each year rather than spread across pay periods, which is a simplification. See the *Timing Assumptions* note on the sidebar for the exact ordering used.

**Steady contribution and withdrawal amounts.** Contributions follow your salary inputs, and withdrawals match the pension allowance exactly. The tool does not model any deviations such as irregular saving, retiring in the middle of the year, or altering your withdrawal rate from year to year.

*Real retirement decisions should involve a licensed financial planner and tax professional who can account for your full situation.*
""")

with st.expander("Limitations on the Results"):
    st.markdown("""
- **The return rate is the biggest factor.** A 1% difference in long-term returns shifts the outcome dramatically between Option A and Option B. Check the break-even rate in the results to see the minimum market return Option B needs to survive retirement.
- **Return sequence is not modeled.** Retiring into a market downturn draws down Option B's fund much faster than a stable average return suggests. This calculator applies the same return rate every year, which is a simplification.
- **Vesting matters for Option A.** If you leave before your pension vests, you may receive little or nothing. This calculator assumes you work your full stated career and collect the full benefit.
- **Both options pay the same annual income.** This is not a comparison about how much you receive each year. Both options pay the same amount. The question is whether Option B has money left over after covering all those payments through retirement.
- **COLA may differ between options.** This model applies the same COLA rate to both the Option A pension payment and the Option B withdrawal amount. In practice they can differ.
""")

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
        help="Your initial salary for the first year you were hired."
    )
    work_years = st.number_input(
        "Years to Work",
        value=30, min_value=1, step=1,
        help="How many years you plan to work before retirement."
    )
    retirement_age = st.number_input(
        "Age at Retirement",
        value=55, min_value=40, max_value=75, step=1,
        help="Your age on the day you expect to retire."
    )
    cola_increase = st.number_input(
        "Cost of Living Adjustment (%)",
        value=3.0, min_value=2.5, max_value=5.5, step=0.1,
        help="Annual salary adjustment announced each October, typically between 2\u20133.5%."
    ) / 100 + 1
    step_increase = st.number_input(
        "Step Increase (%)",
        value=5.5, min_value=0., step=0.1,
        help="Annual raise from step progression. Applies in each of your first 4 years."
    ) / 100 + 1
    promotion_years_input = st.text_input(
        "Promotion Years",
        value="10, 20",
        help="Comma-separated year numbers within your career when you expect a promotion (e.g. 10, 20). Leave blank if none."
    )
    _promo_tokens = [t.strip() for t in promotion_years_input.split(",") if t.strip()]
    _promo_bad = [t for t in _promo_tokens if not t.isdigit()]
    _promo_valid_raw = [int(t) for t in _promo_tokens if t.isdigit()]
    _promo_oob = [y for y in _promo_valid_raw if y < 1 or y > int(work_years)]
    if _promo_bad:
        st.error(f"Can't parse promotion year(s): {', '.join(_promo_bad)}. Enter whole numbers only.")
    elif _promo_oob:
        st.error(f"Promotion year(s) {', '.join(str(y) for y in _promo_oob)} fall outside your {int(work_years)}-year career.")
    promotion_increase = st.number_input(
        "Promotion Increase (%)",
        value=8.0, step=1.,
        help="Expected salary bump each time you are promoted."
    ) / 100 + 1

    st.subheader("Pension")
    pension_contribution_rate = st.number_input(
        "Pension Contribution Rate (%)",
        value=10.0, step=1.,
        help="Percentage of your salary automatically deducted and contributed to the pension system each year."
    ) / 100

    st.markdown("**Starting Pension Allowance**")

    _allowance_mode = st.radio(
        "How to set allowance",
        ["Estimate for me", "Enter manually"],
        horizontal=True,
        label_visibility="collapsed",
    )
    manual_override = (_allowance_mode == "Enter manually")

    if not manual_override:
        # Auto-determine Tier 2 factor from age and years of service
        _t2_age = int(retirement_age)
        _t2_yrs = int(work_years)
        if _t2_age >= 63 and _t2_yrs >= 30:
            _t2_factor = 0.021
            _is_reduced = False
        elif _t2_age >= 60 and _t2_yrs >= 30:
            _t2_factor = 0.020
            _is_reduced = False
        elif _t2_age >= 55 and _t2_yrs >= 30:
            _t2_factor = 0.020
            _is_reduced = False
        elif _t2_yrs >= 30:
            _t2_factor = 0.020
            _is_reduced = True
        elif _t2_age >= 63 and _t2_yrs >= 5:
            _t2_factor = 0.020
            _is_reduced = False
        else:
            _t2_factor = 0.015
            _is_reduced = False

        if _is_reduced:
            _early_red = st.number_input(
                "Early Retirement Reduction (%)",
                value=0.0, min_value=0.0, max_value=50.0, step=0.5,
                help="Your age and years of service qualify for retirement with an early reduction. Enter the exact percentage from your plan's retirement estimator.",
            )
        else:
            _early_red = 0.0

        _promo_yrs = tuple(int(y.strip()) for y in promotion_years_input.split(",") if y.strip().isdigit())
        _fas = compute_fas(starting_wage, int(work_years), cola_increase, step_increase,
                           _promo_yrs, promotion_increase)
        _reduction = 1.0 - _early_red / 100.0
        _computed_allowance = work_years * _fas * _t2_factor * _reduction

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
        help="How many years you expect to spend in retirement before you die."
    )
    index_returns_rate = st.number_input(
        "Index Returns Rate (%)",
        value=10.0, min_value=0.0, max_value=25.0, step=0.1,
        help="Expected annual return on Option B's investment account, in nominal terms (before subtracting inflation). Use a nominal figure here because salaries and pension payments in this calculator are also nominal, growing with your COLA rate. The S&P 500 has averaged about 10% nominally over the long run; a diversified balanced portfolio might return 6 to 8%."
    ) / 100 + 1


promotion_years = tuple(int(y.strip()) for y in promotion_years_input.split(",") if y.strip().isdigit())

result = run_simulation(
    starting_wage, int(work_years), cola_increase, step_increase,
    promotion_years, promotion_increase, pension_contribution_rate,
    starting_allowance, int(retirement_years), index_returns_rate,
)
years = result["years"]
pension_fund_values = result["pension_fund_values"]
personal_fund_values = result["personal_fund_values"]
hover_data = result["hover_data"]
yearly_data = result["yearly_data"]
pension_contribution_total = result["pension_contribution_total"]
pension_redeemed_total = result["pension_redeemed_total"]
personal_balance = result["personal_balance"]

# First retirement year where personal fund goes negative (1-indexed), or None
_depletion_year = next(
    (k for k in range(1, int(retirement_years) + 1)
     if personal_fund_values[int(work_years) + k] < 0),
    None,
)

_breakeven_rate = compute_breakeven_rate(
    starting_wage, int(work_years), cola_increase, step_increase,
    promotion_years, promotion_increase, pension_contribution_rate,
    starting_allowance, int(retirement_years),
)

fig = go.Figure()

_annual_payments = [h[1] for h in hover_data]
fig.add_trace(go.Scatter(
    x=years,
    y=pension_fund_values,
    mode="lines",
    name="Total paid out to date (same for both options)",
    line=dict(color="#78716C", dash="dot", width=1.5),
    customdata=_annual_payments,
    hovertemplate=(
        "<b>Year %{x}</b><br>"
        "This year: $%{customdata:,.0f}<br>"
        "Total: $%{y:,.0f}"
        "<extra></extra>"
    ),
))

fig.add_trace(go.Scatter(
    x=years,
    y=personal_fund_values,
    mode="lines+markers",
    name="Personal fund: money left in the account",
    line=dict(color="#0D9488"),
    customdata=hover_data,
    hovertemplate=(
        "<b>Year %{x}</b><br>"
        "Deposit this year: $%{customdata[2]:,.0f}<br>"
        "Withdrawal this year: $%{customdata[3]:,.0f}<br>"
        "Market returns this year: $%{customdata[4]:,.0f}<br>"
        "Fund balance: $%{y:,.0f}"
        "<extra></extra>"
    ),
))

# Adaptive x-axis
total_years = len(years)
x_tick_step = max(5, int(math.ceil(total_years / 12 / 5) * 5))

# Adaptive y-axis
all_values = [v for v in personal_fund_values if v is not None]
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

fig.update_layout(
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
    ),
    plot_bgcolor="white",
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
    margin=dict(l=40, r=20, t=20, b=120),
)

fig.add_vrect(
    x0=-0.5, x1=int(work_years) + 0.5,
    fillcolor="rgba(148,163,184,0.08)", layer="below", line_width=0,
    annotation_text="Working Years", annotation_position="top left",
    annotation=dict(font_size=11, font_color="#64748B"),
)
fig.add_vrect(
    x0=int(work_years) + 0.5, x1=len(years) - 0.5,
    fillcolor="rgba(217,119,6,0.06)", layer="below", line_width=0,
    annotation_text="Retirement Years", annotation_position="top left",
    annotation=dict(font_size=11, font_color="#D97706"),
)
fig.add_vline(x=int(work_years), line_width=2, line_dash="dash", line_color="#DC2626")
_fund_depletes = min(personal_fund_values) < 0
fig.add_hline(y=0, line_width=2, line_color="#666666",
          annotation_text="$0 = personal fund depleted" if _fund_depletes else "$0",
          annotation_position="bottom right")

st.header("Pension vs. Personal Retirement Fund Over Time")

with st.expander("How to read this chart"):
    st.markdown("""
Both options pay you the **same income every year in retirement**. The comparison comes down to one question: **does the Personal Fund (Option B) run out of money before you die?**

- **Teal line (Option B)** = how much remains in the personal fund after each annual withdrawal. If it stays above zero through all retirement years, Option B wins. If it hits zero, Option A wins.
- **Dotted gray line** = the annual payment amount: what Option A pays each year, which is also exactly what you withdraw from Option B each year. Toggle it on/off with the checkbox below.
- **Background shading** = the blue-gray region is your working years; the warm region is retirement.
- **Red dashed line** = the year retirement begins.
- **Horizontal gray line** = the $0 mark. If the teal line crosses this, Option B has run out of money.
""")

_show_ref_line = st.checkbox("Show annual withdrawal reference line", value=False)
fig.data[0].visible = _show_ref_line

st.plotly_chart(fig, use_container_width=True)

render_result_banner(
    personal_balance, retirement_years, _depletion_year,
    _breakeven_rate, (index_returns_rate - 1) * 100,
)

st.space("small")

_current_rate_pct = (index_returns_rate - 1) * 100
_rate_buffer = _current_rate_pct - _breakeven_rate
_years_covered = int(retirement_years) if _depletion_year is None else _depletion_year - 1

mc1, mc2, mc3 = st.columns(3)
with mc1:
    st.metric(
        label="Pension Contributed",
        value=f"${pension_contribution_total:,.0f}",
        help="The total amount automatically deducted from your paychecks and paid into the pension system over your working years."
    )
with mc2:
    st.metric(
        label="Pension Received",
        value=f"${pension_redeemed_total:,.0f}",
        delta=f"${pension_redeemed_total - pension_contribution_total:,.0f} net",
        help="The total pension income paid out over all retirement years, including annual COLA increases. The delta shows how much more you received than you put in."
    )
with mc3:
    st.metric(
        label="Fund at Retirement",
        value=f"${personal_fund_values[int(work_years)]:,.0f}",
        help="The balance of your hypothetical personal investment account on the day you retire, after years of contributions and market growth."
    )

mc4, mc5, mc6 = st.columns(3)
with mc4:
    if personal_balance > 0:
        st.metric(
            label="Final Fund Balance at Death",
            value=f"${personal_balance:,.0f}",
            delta="Did not run out ✓",
            help="The personal fund still has money left after paying out the same income as the pension for every retirement year. This is money you would still own."
        )
    else:
        st.metric(
            label="Final Fund Balance at Death",
            value=f"${personal_balance:,.0f}",
            delta="Ran out before death ✗",
            delta_color="inverse",
            help="The personal fund was depleted before your retirement years were up. The pension would have continued paying regardless."
        )
with mc5:
    st.metric(
        label="Break-even Return Rate",
        value=f"{_breakeven_rate:.1f}%",
        delta=f"{_rate_buffer:+.1f}pp vs. your {_current_rate_pct:.1f}% assumption",
        delta_color="normal" if _rate_buffer >= 0 else "inverse",
        help="The minimum annual investment return at which the personal fund survives your full retirement period. Compare this to your Index Returns Rate input.",
    )
with mc6:
    st.metric(
        label="Years Fund Covers",
        value=f"{_years_covered} / {int(retirement_years)} yrs",
        delta="Full retirement covered ✓" if _depletion_year is None else f"Ran out {int(retirement_years) - _years_covered} yrs early ✗",
        delta_color="normal" if _depletion_year is None else "inverse",
        help="How many retirement years Option B (personal fund) can sustain the same annual withdrawal as the pension, out of your total retirement period.",
    )

st.markdown("""
**What you leave behind at your death:**
- With **Option B (personal fund)**, whatever the teal line shows at the end of retirement is money you still own (to donate, pass on, etc.)
- With **Option A (pension)**, payments stop when you die (unless you elected a survivor benefit, which is a reduced annual payment to a spouse or dependent after your death). This calculator does not model survivor benefits.
""")

st.divider()
st.header("Year-Over-Year Breakdown")

st.markdown("""
Each row is one year. The left table tracks **Option A (pension)**, while the right tracks **Option B (personal fund)**. They use the same dollar amounts each year so the comparison is apples-to-apples. The bold **Total** row at the bottom of each table ties back to the summary metrics above.
""")

with st.expander("Working Years"):
    st.markdown("""
During your working years, a fixed percentage of your salary is contributed annually. Your salary grows each year from Cost of Living Adjustments (COLA), step increases, and any promotions.
""")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Option A: Pension**")
        st.markdown(f"""
Each year, {pension_contribution_rate*100:.0f}% of your salary is deducted and paid into the pension. The **Contribution** column shows that deduction. The **Total Contributed** column is a running sum of all contributions to date.

Salary grows each year by your COLA ({(cola_increase-1)*100:.1f}%), plus a step increase ({(step_increase-1)*100:.1f}%) in your first 4 years, plus a {(promotion_increase-1)*100:.0f}% bump in any promotion years ({str(promotion_years).strip("[]") if promotion_years else "none entered"}). Year 1 is a special case: it averages your Step 1 and Step 2 salaries, since the Step 1→2 raise happens 6 months in.
""")
    with col2:
        st.markdown("**Option B: Personal Fund**")
        st.markdown(f"""
Instead of paying into the pension, imagine depositing that same amount each year into your own investment account. The column headers show the formula: the **Start Balance** earns **+ Returns** (investment growth at {(index_returns_rate-1)*100:.1f}%/year), then the **+ Deposit** (same as the pension contribution) is added, producing the **= Balance** at year-end.

Returns are calculated on the balance at the *start* of the year, before that year's deposit is added.
""")
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(
            render_breakdown_table(
                yearly_data[["Year", "Salary", "Pension Contribution", "Pension Contribution Total"]],
                "W",
                {"Pension Contribution": "Contribution", "Pension Contribution Total": "Total Contributed"},
            ),
            hide_index=True,
        )
    with col2:
        st.dataframe(
            render_breakdown_table(
                yearly_data[["Year", "Start Balance", "Market Returns", "Pension Contribution", "Balance"]],
                "W",
                {"Market Returns": "+ Returns", "Pension Contribution": "+ Deposit", "Balance": "= Balance"},
                balance_col="= Balance",
            ),
            hide_index=True,
        )

with st.expander("Retirement Years"):
    st.markdown("""
Once you retire, contributions stop. The pension begins paying you a fixed annual allowance that grows each year with COLA. The personal fund is drawn down by that same amount each year, but continues earning investment returns on whatever balance remains. If the **= Balance** ever turns red (negative), the personal fund has run out. The year it first goes red is the year that the pension's lifetime guarantee starts to matter.
""")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Option A: Pension**")
        st.markdown(f"""
The pension pays a set annual amount, growing by {(cola_increase-1)*100:.1f}% each year (COLA). **Pension Received** is that year's payment. **Total Received** is the running sum of all payments to date.
""")
    with col2:
        st.markdown("**Option B: Personal Fund**")
        st.markdown(f"""
Each year, you withdraw the same dollar amount as the pension would have paid. The column headers show the formula: the **Start Balance** earns **+ Returns** ({(index_returns_rate-1)*100:.1f}%/year), then the **− Withdrawal** is subtracted, leaving **= Balance**. If returns exceed the withdrawal, the balance grows. If not, it shrinks.
""")
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(
            render_breakdown_table(
                yearly_data[["Year", "Pension Redeemed", "Pension Redeemed Total"]],
                "R",
                {"Pension Redeemed": "Pension Received", "Pension Redeemed Total": "Total Received"},
            ),
            hide_index=True,
        )
    with col2:
        st.dataframe(
            render_breakdown_table(
                yearly_data[["Year", "Start Balance", "Market Returns", "Pension Redeemed", "Balance"]],
                "R",
                {"Start Balance": "Start Balance",
                 "Market Returns": "+ Returns",
                 "Pension Redeemed": "− Withdrawal",
                 "Balance": "= Balance"},
                balance_col="= Balance",
            ),
            hide_index=True,
        )


st.divider()
st.header("Case Studies")

st.markdown("""
The two examples below show one scenario where each option wins. To see the full charts and tables for either, copy the listed settings into the calculator above.
""")

with st.expander("Case Study A: Personal Fund Wins"):
    st.markdown("""
**Settings:** Starting wage \\$120,000 · Step increase 5.5% · COLA 3% · Promotions at years 10 and 20 (8% each) · Pension contribution rate 10% · Index returns 7% · Work years 30 · Retirement years 30 · First-year pension allowance \\$70,458

---

Alice is a public school administrator who starts at \\$120,000. Across a 30-year career, her salary climbs through step increases, COLA adjustments, and two promotions. Every year, 10% of it goes into the pension.

**The pension:** By the time Alice retires, she has paid about **\\$785,000** into the pension. In return, she gets an allowance that starts around \\$70,458 a year and rises 3% annually. Add up 30 years of those payments and she collects roughly **\\$3.35 million**.

**The personal fund:** Now suppose she had put those same contributions into an account earning 7% a year instead. By retirement it would hold about **\\$2.02 million**. She then withdraws the same amount the pension would have paid each year. Since 7% growth outpaces what she takes out, the balance keeps climbing through retirement and finishes above **\\$6.28 million**.

**Verdict:** The personal fund wins, and it is worth being clear about why. Both options pay Alice the exact same income every year she is retired. The pension never hands her an extra dollar. The whole difference is what is left at the end. The personal fund still holds \\$6.28 million that she owns and can pass to her family, while the pension leaves nothing once she dies.

This is also the scenario people misread most often. They see "\\$3.35 million in pension income" and assume the pension came out ahead, but that number is just the running total of Alice's annual payments; keep in mind that the personal fund paid out that same amount! The \\$6.28 million is *extra* that she gets to keep (donate, pass on, etc.), on top of the \\$3.35 million that she already withdrew and spent during her life.
""")

with st.expander("Case Study B: Pension Wins"):
    st.markdown("""
**Settings:** Starting wage \\$65,000 · Step increase 5.5% · COLA 3% · No promotions · Pension contribution rate 10% · Index returns 5% · Work years 20 · Retirement years 40 · First-year pension allowance \\$27,000

---

Bob is a civil servant who starts at \\$65,000 and works a steady 20 years with no promotions. He retires fairly early and then spends 40 years in retirement before he dies. Over that lifetime the market returns a modest 5% a year.

**The pension:** During his 20 working years, Bob pays about **\\$175,000** into the pension. In retirement he collects around \\$27,000 the first year, rising 3% annually. Stretched over 40 years, that comes to roughly **\\$2 million**, more than 11 times what he put in.

**The personal fund:** Those same contributions, growing at 5% a year, would leave Bob with about **\\$265,000** at retirement. Once he starts pulling out \\$27,000 a year (rising 3% annually), the growth cannot keep up with the withdrawals. The account runs dry in **about 13 years**, leaving nothing for his final 27 years.

**Verdict:** The pension wins because Bob outlives his savings. At 5% returns, a \\$265,000 balance just cannot fund 40 years of withdrawals. What carries him through is the pension's promise to keep paying for as long as he lives. Without it, he runs out of money in his early 70s.

The pension option tends to come out ahead when returns are low, retirement is long, or the personal fund didn't have enough working years to grow.
""")

st.divider()
st.header("Share Your Feedback")
st.caption("What would make this calculator more useful? What's missing, confusing, or surprising?")

if "feedback_key" not in st.session_state:
    st.session_state.feedback_key = 0
if "feedback_success" not in st.session_state:
    st.session_state.feedback_success = False

with st.form("feedback_form"):
    feedback_text = st.text_area(
        "Your feedback",
        height=120,
        placeholder="e.g. I wish it showed the impact of leaving before vesting, or the chart was hard to read...",
        label_visibility="collapsed",
        key=f"feedback_text_{st.session_state.feedback_key}",
    )
    if st.form_submit_button("Submit"):
        if feedback_text.strip():
            (
                ip, country, region, city, zip_code, lat, lon,
                timezone, isp, is_vpn, is_mobile_net,
                lang, referrer, platform_hdr, mobile_hdr,
                browser, browser_ver, os_name, os_ver, device,
            ) = _client_metadata()
            err = _append_feedback([
                datetime.now().isoformat(timespec="seconds"),
                feedback_text.strip(),
                starting_wage, int(work_years), int(retirement_years),
                round((cola_increase - 1) * 100, 2),
                round((index_returns_rate - 1) * 100, 2),
                round(pension_contribution_rate * 100, 2),
                round(starting_allowance, 2),
                round(pension_contribution_total, 2),
                round(pension_redeemed_total, 2),
                round(personal_fund_values[int(work_years)], 2),
                round(personal_balance, 2),
                round(_breakeven_rate, 2),
                _years_covered,
                "Option A" if personal_balance <= 0 else "Option B",
                ip, country, region, city, zip_code, lat, lon,
                timezone, isp, is_vpn, is_mobile_net,
                lang, referrer, platform_hdr, mobile_hdr,
                browser, browser_ver, os_name, os_ver, device,
            ])
            if err:
                st.warning(f"Could not save feedback: {err}")
            else:
                st.session_state.feedback_key += 1
                st.session_state.feedback_success = True
                st.rerun()
        else:
            st.warning("Please enter some feedback before submitting.")

if st.session_state.feedback_success:
    _msg = st.empty()
    _msg.markdown(
        """
        <div style="background:#d4edda;border:1px solid #c3e6cb;color:#155724;
                    padding:.75rem 1.25rem;border-radius:.375rem;margin:.25rem 0;
                    animation:fb_fade .8s ease-in 2.2s forwards">
            ✓ &nbsp;Thank you. Your feedback is noted.
        </div>
        <style>@keyframes fb_fade{from{opacity:1}to{opacity:0}}</style>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(3)
    _msg.empty()
    st.session_state.feedback_success = False
