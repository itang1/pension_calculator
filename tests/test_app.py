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
    at.number_input(key="in_returns").set_value(9.0).run()
    at.number_input(key="in_plan_age").set_value(95).run()
    at.number_input(key="in_inflation").set_value(4.0).run()
    at.text_input(key="in_promo_years").set_value("ten").run()
    assert at.error, "expected an input error"
    at.text_input(key="in_promo_years").set_value("").run()
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
    at.text_input(key="in_promo_years").set_value("²").run()
    assert not at.exception
    assert at.error


def _flat_career(at, hire_age, retirement_age):
    """No raises at all, so dollar figures are easy to check by hand."""
    at.text_input(key="in_promo_years").set_value("").run()
    at.number_input(key="in_cola").set_value(0.0).run()
    at.number_input(key="in_step_count").set_value(0).run()
    at.number_input(key="in_wage").set_value(100000).run()
    at.number_input(key="in_hire_age").set_value(hire_age).run()
    at.number_input(key="in_retirement_age").set_value(retirement_age).run()


def test_unvested_compares_refund_with_your_account():
    # 4 years x $10,000 deposits: refund at 6.5% interest is $44,072; the
    # account at 0% holds $40,000, so the refund wins.
    at = _app(real="false")
    _flat_career(at, 51, 55)
    at.number_input(key="in_returns").set_value(0.0).run()
    assert not at.exception and not at.error
    banner = next(m.value for m in at.markdown if "refund of your contributions" in m.value)
    assert "refund of your contributions" in banner
    assert "The contribution refund is larger than your account" in banner
    assert _metric(at, "Refund When You Leave") == "$44,072"
    assert _metric(at, "Your Account When You Leave") == "$40,000"
    # Above the refund's 6.5% interest, your own account wins instead.
    at.number_input(key="in_returns").set_value(7.0).run()
    banner = next(m.value for m in at.markdown if "refund of your contributions" in m.value)
    assert "Your account is larger than the refund" in banner


def test_manual_amount_keeps_the_plans_start_age_and_cola():
    # Hired at 35, leaving at 55 with 20 years: the plan defers the pension to
    # 60 with no COLA. Typing the amount by hand must not change that.
    at = _app()
    _flat_career(at, 35, 55)
    auto = at.session_state["_inputs"]
    assert auto["deferral_years"] == 5 and auto["retiree_cola"] == 1.0
    at.radio(key="in_allowance_mode").set_value("Enter manually").run()
    at.radio(key="in_allowance_basis").set_value("Dollars at retirement").run()
    at.number_input(key="allowance_manual").set_value(30000).run()
    manual = at.session_state["_inputs"]
    assert manual["deferral_years"] == 5 and manual["retiree_cola"] == 1.0
    assert manual["starting_allowance"] == 30000
    assert any("payments start at age 60" in c.value for c in at.caption)


def test_earlier_hires_are_told_the_rules_do_not_apply():
    at = _app()
    at.number_input(key="in_hire_year").set_value(2010).run()
    warning = next(w.value for w in at.warning if "calculator is designed" in w.value)
    assert "hired in or after 2014" in warning
    assert "does not model the pension rules" in warning
    assert "Entering a manual pension amount does not change when payments start" in warning


def test_case_study_button_sets_the_swings_its_figures_assume():
    at = _app()
    at.session_state["mc_std"] = 0.0
    at.run()
    next(b for b in at.button if b.key == "load_alice").click().run()
    at.run()
    assert at.session_state["mc_std"] == 15.0
    assert any("38 out of 100" in c.value for c in at.caption)


def test_loading_a_link_fills_inputs_then_clears_the_address_bar():
    at = _app(wage="90000", hire_age="30", retirement_age="60")
    assert at.session_state["in_wage"] == 90000 and at.session_state["in_hire_age"] == 30
    assert dict(at.query_params) == {}


def test_share_link_is_made_on_request_with_only_active_inputs():
    at = _app()
    assert not at.code  # nothing until asked
    next(b for b in at.button if b.key == "make_share_link").click().run()
    link = at.code[0].value
    assert "wage=120000" in link and "hire_age=25" in link
    assert "allowance_manual" not in link and "current_wage" not in link
    at.radio(key="in_allowance_mode").set_value("Enter manually").run()
    assert "allowance_manual=" in at.code[0].value


def test_feedback_leaves_calculator_details_out_unless_ticked(monkeypatch):
    import common
    rows = []
    monkeypatch.setattr(common, "_append_feedback", lambda row: rows.append(row))
    monkeypatch.setattr(common, "_client_metadata", lambda: ("x",) * 20)
    at = _app()
    at.text_area[0].input("Helpful, thanks").run()
    next(b for b in at.button if b.label == "Submit").click().run()
    assert rows, "feedback was not submitted"
    row = rows[-1]
    assert row[1] == "Helpful, thanks"
    assert all(v == "" for v in row[2:16])          # calculator details left blank
    assert row[-2:] == ["", ""]                     # swing details left blank


def test_late_hire_is_not_blocked_by_example_promotions():
    at = _app()
    at.number_input(key="in_hire_age").set_value(50).run()
    at.number_input(key="in_retirement_age").set_value(63).run()
    assert not at.exception and not at.error
    assert at.session_state["_inputs"]["promotion_years"] == (10,)
    assert at.warning
    assert at.session_state["_inputs"]["retirement_years"] == 22


def test_invalid_planning_age_can_be_fixed_without_losing_inputs():
    at = _app()
    at.number_input(key="in_plan_age").set_value(50).run()
    assert at.error and not at.exception
    at.number_input(key="in_plan_age").set_value(90).run()
    assert not at.error and not at.exception
    assert at.session_state["_inputs"]["retirement_years"] == 35


def test_monthly_entry_preserves_amount_across_unit_changes():
    at = _app()
    at.radio(key="in_allowance_mode").set_value("Enter manually").run()
    at.radio(key="in_allowance_basis").set_value("Dollars at retirement").run()
    at.number_input(key="allowance_manual").set_value(30000.0).run()
    at.radio(key="in_allowance_period").set_value("Monthly").run()
    assert not at.exception
    assert at.session_state["allowance_manual"] == pytest.approx(2500)
    assert at.session_state["_inputs"]["starting_allowance"] == pytest.approx(30000)
    at.number_input(key="allowance_manual").set_value(3500.0).run()
    at.radio(key="in_allowance_period").set_value("Yearly").run()
    assert at.session_state["allowance_manual"] == pytest.approx(42000)
    assert at.session_state["_inputs"]["starting_allowance"] == pytest.approx(42000)


def test_examples_can_restore_manual_inputs_and_display_preferences():
    import common
    at = _app()
    at.radio(key="in_allowance_mode").set_value("Enter manually").run()
    at.radio(key="in_allowance_period").set_value("Monthly").run()
    at.number_input(key="allowance_manual").set_value(3500.0).run()
    at.number_input(key="in_plan_age").set_value(91).run()
    at.toggle(key="in_real").set_value(False).run()
    before = {k: at.session_state[k] for k in common._SHARE_SPEC if k in at.session_state}
    at.button(key="load_alice").click().run()
    at.run()
    at.button(key="load_bob").click().run()
    at.run()
    at.button(key="restore_inputs").click().run()
    assert not at.exception and not at.error
    for key, value in before.items():
        assert at.session_state[key] == value, key
    assert at.session_state["_inputs"]["allowance_source"] == "manual"


def test_monthly_and_planning_age_round_trip_in_shared_links():
    from urllib.parse import parse_qsl, urlsplit
    at = _app()
    at.radio(key="in_allowance_mode").set_value("Enter manually").run()
    at.radio(key="in_allowance_period").set_value("Monthly").run()
    at.number_input(key="allowance_manual").set_value(3123.45).run()
    at.number_input(key="in_plan_age").set_value(96).run()
    at.button(key="make_share_link").click().run()
    other = _app(**dict(parse_qsl(urlsplit(at.code[0].value).query)))
    assert not other.exception and not other.error
    assert other.session_state["_inputs"] == at.session_state["_inputs"]


def test_bad_monthly_link_amount_does_not_exceed_widget_limit():
    at = _app(allowance_mode="Enter manually", allowance_period="Monthly", allowance_manual="9000000")
    assert not at.exception


def test_older_links_keep_their_original_retirement_duration():
    at = _app(retirement_age="63", retirement_years="25")
    assert at.session_state["in_plan_age"] == 88
    assert at.session_state["_inputs"]["retirement_years"] == 25


def test_dollar_display_changes_amounts_not_funding_or_return_assumptions():
    at = _app()
    real = at.session_state["_results"]
    assert at.session_state["in_real"] is True
    at.toggle(key="in_real").set_value(False).run()
    nominal = at.session_state["_results"]
    assert real["depletion_year"] == nominal["depletion_year"]
    assert real["years_covered"] == nominal["years_covered"]
    assert real["breakeven_rate"] == nominal["breakeven_rate"]
    assert real["index_return_pct"] == pytest.approx(10.0)
    assert real["pension_redeemed_total"] < nominal["pension_redeemed_total"]
    assert any("7.3%" in m.value and "rising prices" in m.value for m in at.markdown)


def test_inflation_caps_pension_increases_without_replacing_salary_raise():
    at = _app()
    original_salary_raise = at.session_state["_inputs"]["cola_increase"]
    at.number_input(key="in_inflation").set_value(1.0).run()
    assert at.session_state["_inputs"]["retiree_cola"] == pytest.approx(1.01)
    at.number_input(key="in_inflation").set_value(5.0).run()
    assert at.session_state["_inputs"]["retiree_cola"] == pytest.approx(1.02)
    assert at.session_state["_inputs"]["cola_increase"] == original_salary_raise
