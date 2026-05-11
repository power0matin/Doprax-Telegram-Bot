from bot.i18n import I18N


def test_i18n_basic_en() -> None:
    assert "Choose" in I18N.t("en", "choose_lang")


def test_i18n_basic_fa() -> None:
    assert "زبان" in I18N.t("fa", "choose_lang")


def test_i18n_fallback_key() -> None:
    # missing key returns key
    assert I18N.t("en", "missing_key_123") == "missing_key_123"


def test_i18n_formatting_safe() -> None:
    # formatting failure should not crash
    s = I18N.t("en", "something_wrong", ref="abc")
    assert "abc" in s
