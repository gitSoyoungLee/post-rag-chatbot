from post_rag.rates import EmsRateCalculator, parse_ems_nondocument_rates


def test_rate_parser_extracts_country_tables() -> None:
    rates = parse_ems_nondocument_rates()

    assert rates["US"][0] == (0.5, 39000)
    assert rates["JP"][2] == (1.0, 28500)
    assert rates["3"][0] == (0.5, 37500)


def test_ems_rate_uses_next_weight_bracket() -> None:
    result = EmsRateCalculator().calculate("US", 1500)

    assert result is not None
    assert result.bracket_kg == 1.5
    assert result.amount_krw == 57000


def test_ems_rate_is_not_calculated_for_unsupported_country() -> None:
    assert EmsRateCalculator().calculate("AD", 1500) is None

