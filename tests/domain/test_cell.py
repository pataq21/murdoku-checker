import pytest
from pydantic import ValidationError

from murdoku_checker.domain import Cell


def test_cell_defaults_features_to_absent() -> None:
    cell = Cell(latitude=1, longitude=2)

    assert cell.latitude == 1
    assert cell.longitude == 2
    assert cell.has_carpet is False
    assert cell.has_plant is False
    assert cell.has_sofa is False
    assert cell.has_chair is False


def test_cell_accepts_explicit_features() -> None:
    cell = Cell(
        latitude=0,
        longitude=0,
        has_carpet=True,
        has_plant=True,
        has_sofa=True,
        has_chair=True,
    )

    assert cell.has_carpet
    assert cell.has_plant
    assert cell.has_sofa
    assert cell.has_chair


@pytest.mark.parametrize("coordinate", [-1, -10])
def test_cell_rejects_negative_coordinates(coordinate: int) -> None:
    with pytest.raises(ValidationError) as error:
        Cell(latitude=coordinate, longitude=0)

    assert error.value.errors()[0]["type"] == "greater_than_equal"


@pytest.mark.parametrize("coordinate", [True, 1.5, "1"])
def test_cell_rejects_non_integer_coordinates(coordinate: object) -> None:
    with pytest.raises(ValidationError) as error:
        Cell(latitude=coordinate, longitude=0)  # type: ignore[arg-type]

    assert error.value.errors()[0]["type"] == "int_type"


def test_cell_rejects_non_boolean_features() -> None:
    with pytest.raises(ValidationError) as error:
        Cell(latitude=0, longitude=0, has_sofa=1)  # type: ignore[arg-type]

    assert error.value.errors()[0]["type"] == "bool_type"


def test_cell_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        Cell(latitude=0, longitude=0, color="red")  # type: ignore[call-arg]

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_cell_is_immutable() -> None:
    cell = Cell(latitude=0, longitude=0)

    with pytest.raises(ValidationError) as error:
        cell.latitude = 1  # type: ignore[misc]

    assert error.value.errors()[0]["type"] == "frozen_instance"
