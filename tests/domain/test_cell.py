import pytest
from pydantic import ValidationError

from murdoku_checker.domain import Cell, CellFeature


def test_cell_defaults_features_to_absent() -> None:
    cell = Cell(latitude=1, longitude=2, room="comedor")

    assert cell.latitude == 1
    assert cell.longitude == 2
    assert cell.room == "comedor"
    assert cell.features == ()


def test_cell_accepts_explicit_features() -> None:
    cell = Cell(
        latitude=0,
        longitude=0,
        room="dormitorio",
        features=[CellFeature.BED, CellFeature.PLANT],
    )

    assert cell.features == (CellFeature.BED, CellFeature.PLANT)


def test_cell_rejects_empty_room() -> None:
    with pytest.raises(ValidationError) as error:
        Cell(latitude=0, longitude=0, room="")

    assert error.value.errors()[0]["type"] == "string_too_short"


def test_cell_rejects_non_string_room() -> None:
    with pytest.raises(ValidationError) as error:
        Cell(latitude=0, longitude=0, room=1)  # type: ignore[arg-type]

    assert error.value.errors()[0]["type"] == "string_type"


@pytest.mark.parametrize("coordinate", [-1, -10])
def test_cell_rejects_negative_coordinates(coordinate: int) -> None:
    with pytest.raises(ValidationError) as error:
        Cell(latitude=coordinate, longitude=0, room="comedor")

    assert error.value.errors()[0]["type"] == "greater_than_equal"


@pytest.mark.parametrize("coordinate", [True, 1.5, "1"])
def test_cell_rejects_non_integer_coordinates(coordinate: object) -> None:
    with pytest.raises(ValidationError) as error:
        Cell(latitude=coordinate, longitude=0, room="comedor")  # type: ignore[arg-type]

    assert error.value.errors()[0]["type"] == "int_type"


def test_cell_rejects_string_features_in_python() -> None:
    with pytest.raises(ValidationError) as error:
        Cell(
            latitude=0,
            longitude=0,
            room="comedor",
            features=["chair"],  # type: ignore[list-item]
        )

    assert error.value.errors()[0]["type"] == "is_instance_of"


def test_cell_validates_features_from_json() -> None:
    cell = Cell.model_validate_json(
        '{"latitude":0,"longitude":0,"room":"comedor","features":["chair"]}'
    )

    assert cell.features == (CellFeature.CHAIR,)


def test_cell_rejects_unknown_feature_from_json() -> None:
    with pytest.raises(ValidationError) as error:
        Cell.model_validate_json(
            '{"latitude":0,"longitude":0,"room":"comedor","features":["unknown"]}'
        )

    assert error.value.errors()[0]["type"] == "enum"


def test_cell_rejects_duplicate_features() -> None:
    with pytest.raises(ValidationError, match="duplicate cell feature"):
        Cell(
            latitude=0,
            longitude=0,
            room="comedor",
            features=[CellFeature.CHAIR, CellFeature.CHAIR],
        )


def test_cell_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        Cell(latitude=0, longitude=0, room="comedor", color="red")  # type: ignore[call-arg]

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_cell_is_immutable() -> None:
    cell = Cell(latitude=0, longitude=0, room="comedor")

    with pytest.raises(ValidationError) as error:
        cell.latitude = 1  # type: ignore[misc]

    assert error.value.errors()[0]["type"] == "frozen_instance"
