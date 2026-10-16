import pytest
from pydantic import ValidationError

from murdoku_checker.domain import Cell, Map


def test_map_can_be_empty() -> None:
    map_ = Map()

    assert map_.cells == ()
    assert map_.get_cell(0, 0) is None


def test_map_stores_and_finds_cells() -> None:
    first = Cell(latitude=0, longitude=1, has_plant=True)
    second = Cell(latitude=3, longitude=2, has_chair=True)

    map_ = Map(cells=[first, second])

    assert map_.cells == (first, second)
    assert map_.get_cell(0, 1) is first
    assert map_.get_cell(3, 2) is second
    assert map_.get_cell(1, 1) is None


def test_map_rejects_duplicate_coordinates() -> None:
    cells = [
        Cell(latitude=1, longitude=2, has_carpet=True),
        Cell(latitude=1, longitude=2, has_sofa=True),
    ]

    with pytest.raises(ValidationError, match="duplicate cell coordinates") as error:
        Map(cells=cells)

    assert error.value.errors()[0]["loc"] == ("cells",)


def test_map_rejects_non_cell_items() -> None:
    with pytest.raises(ValidationError) as error:
        Map(cells=["not a cell"])  # type: ignore[list-item]

    assert error.value.errors()[0]["loc"] == ("cells", 0)


def test_map_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        Map(cells=(), name="invalid")  # type: ignore[call-arg]

    assert error.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("coordinate", [-1, True, 1.5])
def test_get_cell_validates_coordinates(coordinate: object) -> None:
    map_ = Map()

    with pytest.raises(ValidationError):
        map_.get_cell(coordinate, 0)  # type: ignore[arg-type]


def test_map_is_immutable() -> None:
    map_ = Map(cells=[Cell(latitude=0, longitude=0)])

    with pytest.raises(ValidationError) as error:
        map_.cells = ()  # type: ignore[misc]

    assert error.value.errors()[0]["type"] == "frozen_instance"


def test_map_serializes_cells_without_private_index() -> None:
    cell = Cell(latitude=1, longitude=2, has_sofa=True)
    map_ = Map(cells=[cell])

    assert map_.model_dump() == {
        "cells": (
            {
                "latitude": 1,
                "longitude": 2,
                "has_carpet": False,
                "has_plant": False,
                "has_sofa": True,
                "has_chair": False,
            },
        )
    }
    assert '"_cells_by_position"' not in map_.model_dump_json()