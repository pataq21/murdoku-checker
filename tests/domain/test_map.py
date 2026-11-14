import pytest
from pydantic import ValidationError

from murdoku_checker.domain import GridCell, Map, Room


def test_map_can_be_empty() -> None:
    map_ = Map()

    assert map_.cells == ()
    assert map_.get_cell(0, 0) is None


def test_map_stores_and_finds_cells() -> None:
    first = GridCell(
        latitude=0,
        longitude=1,
        room="comedor",
        features=["plant"],
    )
    second = GridCell(
        latitude=3,
        longitude=2,
        room="cocina",
        features=["chair"],
    )

    map_ = Map(cells=[first, second])

    assert map_.cells == (first, second)
    assert map_.get_cell(0, 1) is first
    assert map_.get_cell(3, 2) is second
    assert map_.get_cell(1, 1) is None


def test_map_rejects_duplicate_coordinates() -> None:
    cells = [
        GridCell(latitude=1, longitude=2, room="comedor"),
        GridCell(latitude=1, longitude=2, room="cocina"),
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
    map_ = Map(cells=[GridCell(latitude=0, longitude=0, room="comedor")])

    with pytest.raises(ValidationError) as error:
        map_.cells = ()  # type: ignore[misc]

    assert error.value.errors()[0]["type"] == "frozen_instance"


def test_map_serializes_cells_without_private_index() -> None:
    cell = GridCell(
        latitude=1,
        longitude=2,
        room="cocina",
        features=["counter"],
    )
    map_ = Map(cells=[cell])

    assert map_.model_dump() == {
        "cells": (
            {
                "latitude": 1,
                "longitude": 2,
                "room": "cocina",
                "features": ("counter",),
            },
        )
    }
    assert '"_cells_by_position"' not in map_.model_dump_json()

def test_map_groups_cells_into_rooms_sorted_by_name() -> None:
    kitchen = GridCell(latitude=0, longitude=0, room="cocina", features=["oven"])
    dining = GridCell(latitude=0, longitude=1, room="comedor", features=["oven"])
    pantry = GridCell(latitude=1, longitude=0, room="cocina")
    map_ = Map(cells=[dining, kitchen, pantry])
    cocina = map_.get_room("cocina")

    assert [room.name for room in map_.rooms] == ["cocina", "comedor"]
    assert cocina == Room(name="cocina", cells=(kitchen, pantry))
    assert cocina is not None and cocina.positions == {(0, 0), (1, 0)}
    assert map_.get_room("salon") is None
    assert map_.positions == {(0, 0), (0, 1), (1, 0)}
    assert map_.feature_positions("oven") == {(0, 0), (0, 1)}


def test_room_rejects_cells_of_another_room() -> None:
    with pytest.raises(ValidationError, match="belongs to room 'comedor'"):
        Room(
            name="cocina",
            cells=(GridCell(latitude=0, longitude=0, room="comedor"),),
        )
