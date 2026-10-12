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
