from post_rag.countries import CountryRepository


def test_country_lookup_by_code_and_name() -> None:
    repository = CountryRepository()

    by_code = repository.find("US")
    by_name = repository.find("미국")

    assert by_code is not None
    assert by_name is not None
    assert by_code.code == by_name.code == "US"
    assert any(service.service == "ems" for service in by_code.services)

