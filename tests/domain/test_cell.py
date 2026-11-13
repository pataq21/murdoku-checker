import pytest
from pydantic import ValidationError

from murdoku_checker.domain import Cell


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
        features=["bed", "plant"],
    )

    assert cell.features == ("bed", "plant")


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


def test_cell_rejects_empty_feature_name() -> None:
    with pytest.raises(ValidationError) as error:
        Cell(
            latitude=0,
            longitude=0,
            room="comedor",
            features=[""],
        )

    assert error.value.errors()[0]["type"] == "string_too_short"


def test_cell_validates_features_from_json() -> None:
    cell = Cell.model_validate_json(
        '{"latitude":0,"longitude":0,"room":"comedor","features":["chair"]}'
    )

    assert cell.features == ("chair",)


def test_cell_rejects_duplicate_features() -> None:
    with pytest.raises(ValidationError, match="duplicate cell feature"):
        Cell(
            latitude=0,
            longitude=0,
            room="comedor",
            features=["chair", "chair"],
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
