import json
import random

import pytest
from pydantic import ValidationError

from murdoku_checker.apps.solution_creator import generate_specification
from murdoku_checker.domain import GenerationConfig


def test_config_reads_json_and_derives_board_counts() -> None:
    config = GenerationConfig.model_validate_json(
        '{"rows": 3, "columns": 5, "element_coverage_percent": 40, '
        '"element_type_count": 3, "room_count": 3, "seed": 17}'
    )

    assert config.person_count == 3
    assert config.cell_count == 15
    assert config.element_cell_count == 6


@pytest.mark.parametrize(
    ("percent", "expected"), [(5, 0), (15, 2), (25, 2), (35, 4)]
)
def test_coverage_rounds_to_nearest_with_even_ties(
    percent: int, expected: int
) -> None:
    config = GenerationConfig(
        rows=2,
        columns=5,
        element_coverage_percent=percent,
        element_type_count=min(1, expected),
        room_count=1,
    )

    assert config.element_cell_count == expected


@pytest.mark.parametrize(
    ("percent", "types", "rooms", "message"),
    [
        (5, 3, 3, "not enough element cells"),
        (100, 0, 3, "positive element coverage"),
        (0, 0, 10, "room_count cannot exceed"),
    ],
)
def test_config_rejects_incompatible_requirements(
    percent: int, types: int, rooms: int, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        GenerationConfig(
            rows=3,
            columns=3,
            element_coverage_percent=percent,
            element_type_count=types,
            room_count=rooms,
        )


@pytest.mark.parametrize(
    "invalid_json",
    [
        '{"rows": 0, "columns": 3}',
        '{"rows": 3, "columns": -1}',
        '{"rows": "3", "columns": 3}',
        '{"rows": true, "columns": 3}',
        '{"rows": 3, "columns": 3, "element_coverage_percent": 101}',
        '{"rows": 3, "columns": 3, "element_coverage_percent": -1}',
        '{"rows": 3, "columns": 3, "element_coverage_percent": NaN}',
        '{"rows": 3, "columns": 3, "element_type_count": -1}',
        '{"rows": 3, "columns": 3, "room_count": 0}',
        '{"rows": 3, "columns": 3, "seed": "17"}',
        '{"rows": 3, "columns": 3, "unexpected": 1}',
    ],
)
def test_config_rejects_invalid_fields(invalid_json: str) -> None:
    data = {
        "element_coverage_percent": 0,
        "element_type_count": 0,
        "room_count": 1,
    }
    data.update(json.loads(invalid_json))
    with pytest.raises(ValidationError):
        GenerationConfig.model_validate(data)


def test_generation_is_repeatable_without_changing_global_random_state() -> None:
    config = GenerationConfig(
        rows=5,
        columns=5,
        element_coverage_percent=40,
        element_type_count=3,
        room_count=3,
        seed=17,
    )
    state = random.getstate()

    assert generate_specification(config) == generate_specification(config)
    assert random.getstate() == state


def test_zero_rounded_coverage_generates_no_elements() -> None:
    config = GenerationConfig(
        rows=3,
        columns=3,
        element_coverage_percent=5,
        element_type_count=0,
        room_count=3,
        seed=17,
    )

    assert generate_specification(config).elements == ()


def test_random_sizes_and_counts_always_fill_budget_and_include_every_type() -> None:
    observed_sizes: set[int] = set()
    observed_occupiability: set[bool] = set()
    for budget in range(1, 11):
        for type_count in range(1, budget + 1):
            for seed in range(10):
                config = GenerationConfig(
                    rows=2,
                    columns=5,
                    element_coverage_percent=budget * 10,
                    element_type_count=type_count,
                    room_count=3,
                    seed=seed,
                )
                specification = generate_specification(config)

                assert specification.config == config
                assert len(specification.elements) == type_count
                assert len(
                    {item.element.name for item in specification.elements}
                ) == type_count
                assert sum(
                    item.size * item.count for item in specification.elements
                ) == budget
                for item in specification.elements:
                    assert item.count >= 1
                    assert item.size in (1, 2)
                    observed_sizes.add(item.size)
                    observed_occupiability.add(item.element.is_occupiable)

    assert observed_sizes == {1, 2}
    assert observed_occupiability == {False, True}
