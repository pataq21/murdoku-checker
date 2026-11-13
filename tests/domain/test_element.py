import pytest
from pydantic import ValidationError

from murdoku_checker.domain import Element, Elements


def test_element_defaults_to_not_occupiable() -> None:
    element = Element(name="rock")

    assert element.name == "rock"
    assert element.is_occupiable is False


def test_element_accepts_explicit_occupiable_value() -> None:
    assert Element(name="carpet", is_occupiable=True).is_occupiable is True


def test_element_requires_non_empty_name() -> None:
    with pytest.raises(ValidationError):
        Element(name="")


def test_elements_reject_duplicate_names() -> None:
    with pytest.raises(ValidationError, match="duplicate element name"):
        Elements(elements=(Element(name="tree"), Element(name="tree")))


def test_elements_gets_element_by_name() -> None:
    rock = Element(name="rock")
    elements = Elements(elements=(rock,))

    assert elements.get("rock") is rock
    assert elements.get("tree") is None
