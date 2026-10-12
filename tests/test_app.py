"""End-to-end checks that run the real Streamlit app with AppTest.

The unit tests cover the math; these cover how inputs, errors, links, and
pages connect, which is where the external review found most of its bugs.
"""

import pytest
from streamlit.testing.v1 import AppTest

APP = "pension_calculator.py"


def _app(**params):
    at = AppTest.from_file(APP, default_timeout=120)
    if params:
        at.query_params.update(params)
    at.run()
    return at


def _metric(at, starts_with):
    return next(m.value for m in at.metric if m.label.startswith(starts_with))


def test_default_page_renders_without_errors():
    at = _app()
    assert not at.exception
    assert any(h.value == "Your Result" for h in at.header)


def test_fixing_an_input_error_keeps_other_inputs():
    # An invalid combination used to st.stop() mid-sidebar, so every widget
    # below it was forgotten and snapped back to its default.
    at = _app()
    at.sidebar.number_input(key="in_returns").set_value(9.0).run()
    at.sidebar.number_input(key="in_retirement_years").set_value(40).run()
    at.sidebar.number_input(key="in_inflation").set_value(4.0).run()
    at.sidebar.number_input(key="in_hire_age").set_value(50).run()   # promotions 10, 20 no longer fit
    assert at.error, "expected an input error"
    at.sidebar.text_input(key="in_promo_years").set_value("").run()
    assert not at.error and not at.exception
    assert at.session_state["in_returns"] == 9.0
    assert at.session_state["in_retirement_years"] == 40
    assert at.session_state["in_inflation"] == 4.0


@pytest.mark.parametrize("params", [
    {"wage": "inf"},
    {"hire_age": "1e309"},
    {"work_years": "inf"},
    {"returns": "nan"},
    {"wage": "12.5"},
])
def test_malformed_links_never_crash(params):
    at = _app(**params)
    assert not at.exception


def test_unusual_digits_in_promotion_years_show_an_error_not_a_crash():
    at = _app()
    at.sidebar.text_input(key="in_promo_years").set_value("²").run()
    assert not at.exception
    assert at.error


def _flat_career(at, hire_age, retirement_age):
    """No raises at all, so dollar figures are easy to check by hand."""
    at.sidebar.text_input(key="in_promo_years").set_value("").run()
    at.sidebar.number_input(key="in_cola").set_value(0.0).run()
    at.sidebar.number_input(key="in_step_count").set_value(0).run()
    at.sidebar.number_input(key="in_wage").set_value(100000).run()
    at.sidebar.number_input(key="in_hire_age").set_value(hire_age).run()
    at.sidebar.number_input(key="in_retirement_age").set_value(retirement_age).run()


def test_unvested_compares_refund_with_your_account():
    # 4 years x $10,000 deposits: refund at 6.5% interest is $44,072; the
    # account at 0% holds $40,000, so the refund wins.
    at = _app()
    _flat_career(at, 51, 55)
    at.sidebar.number_input(key="in_returns").set_value(0.0).run()
    assert not at.exception and not at.error
    banner = next(m.value for m in at.markdown if "🏆" in m.value)
    assert "refund of your contributions" in banner
    assert "Winner: The pension's refund" in banner
    assert _metric(at, "Refund When You Leave") == "$44,072"
    assert _metric(at, "Your Account When You Leave") == "$40,000"
    # Above the refund's 6.5% interest, your own account wins instead.
    at.sidebar.number_input(key="in_returns").set_value(7.0).run()
    banner = next(m.value for m in at.markdown if "🏆" in m.value)
    assert "Winner: Your own account" in banner


def test_manual_amount_keeps_the_plans_start_age_and_cola():
    # Hired at 35, leaving at 55 with 20 years: the plan defers the pension to
    # 60 with no COLA. Typing the amount by hand must not change that.
    at = _app()
    _flat_career(at, 35, 55)
    auto = at.session_state["_inputs"]
    assert auto["deferral_years"] == 5 and auto["retiree_cola"] == 1.0
    at.sidebar.radio(key="in_allowance_mode").set_value("Enter manually").run()
    at.sidebar.radio(key="in_allowance_basis").set_value("Dollars at retirement").run()
    at.sidebar.number_input(key="allowance_manual").set_value(30000).run()
    manual = at.session_state["_inputs"]
    assert manual["deferral_years"] == 5 and manual["retiree_cola"] == 1.0
    assert manual["starting_allowance"] == 30000
    assert any("payments start at age 60" in c.value for c in at.sidebar.caption)


def test_earlier_hires_are_told_the_rules_do_not_apply():
    at = _app()
    at.sidebar.number_input(key="in_hire_year").set_value(2010).run()
    assert any("hired before 2014" in w.value for w in at.sidebar.warning)
