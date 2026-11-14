import pytest
from ortools.sat.python import cp_model

from murdoku_checker.apps.solution_checker import OptimizationModel
from murdoku_checker.apps.solution_checker.constraint_builder import ConstraintBuilder
from murdoku_checker.apps.solution_checker.variable_builder import VariableBuilder
from murdoku_checker.domain import (
    AnyOfRule,
    BaseRule,
    Element,
    Elements,
    FeatureElement,
    GridCell,
    InRule,
    Map,
    MurdokuInput,
    NotNextToRule,
    People,
    RoomElement,
    Rules,
)
from murdoku_checker.domain.person import Gender, Person

#  (0,0) a/carpet  (0,1) a
#  (1,0) b         (1,1) b/carpet
CELLS = (
    GridCell(latitude=0, longitude=0, room="a", features=("carpet",)),
    GridCell(latitude=0, longitude=1, room="a"),
    GridCell(latitude=1, longitude=0, room="b"),
    GridCell(latitude=1, longitude=1, room="b", features=("carpet",)),
)


def count_solutions(*rules: BaseRule) -> int:
    input_ = MurdokuInput(
        map=Map(cells=CELLS),
        elements=Elements(
            elements=(Element(name="carpet", is_occupiable=True),)
        ),
        people=People(
            people=(
                Person(name="Alice", gender=Gender.FEMALE),
                Person(name="Bob", gender=Gender.MALE),
            )
        ),
        rules=Rules(rules=rules),
    )
    model = cp_model.CpModel()
    variables = VariableBuilder(model).build(input_)
    builder = ConstraintBuilder(model)
    builder.build_person_constraints(input_, variables)
    builder.build_rule_constraints(input_, variables)
    return OptimizationModel(input_, model, variables).solve(max_solutions=None)


def room(name: str, *, is_unique: bool) -> InRule:
    return InRule(person="Alice", element=RoomElement(value=name), is_unique=is_unique)


def any_of(*conditions: BaseRule) -> AnyOfRule:
    return AnyOfRule(person="Alice", conditions=conditions)


def test_non_unique_in_does_not_constrain_other_people() -> None:
    # Alice in room a (2 cells), Bob anywhere (4 cells).
    assert count_solutions(room("a", is_unique=False)) == 8


def test_unique_room_excludes_other_people() -> None:
    # Alice in room a (2 cells), Bob only in room b (2 cells).
    assert count_solutions(room("a", is_unique=True)) == 4


def test_unique_feature_excludes_other_people_from_its_cells() -> None:
    carpet = InRule(
        person="Alice", element=FeatureElement(value="carpet"), is_unique=True
    )

    # Alice on one carpet cell, Bob on one of the 2 cells without carpet.
    assert count_solutions(carpet) == 4


def test_unique_in_any_of_only_applies_to_its_branch() -> None:
    condition = any_of(room("a", is_unique=True), room("b", is_unique=False))

    # Alice in a: Bob in b (2 * 2). Alice in b: Bob anywhere (2 * 4).
    assert count_solutions(condition) == 12


def test_unique_in_nested_any_of_applies_to_its_branch() -> None:
    inner = any_of(room("a", is_unique=True), room("b", is_unique=True))
    condition = any_of(
        inner, InRule(person="Alice", element=FeatureElement(value="carpet"))
    )

    # Alice alone in her room: 4 cells * 2 for Bob. The carpet branch adds the
    # cases where Bob shares her room: 2 carpet cells * 2.
    assert count_solutions(condition) == 12


@pytest.mark.parametrize(("nested", "expected"), [(False, 10), (True, 12)])
def test_not_next_to_with_unique_in_any_of(nested: bool, expected: int) -> None:
    not_next_to = NotNextToRule(person="Alice", element=FeatureElement(value="carpet"))
    condition = any_of(
        room("a", is_unique=True),
        (
            any_of(not_next_to, room("b", is_unique=True))
            if nested
            else not_next_to
        ),
    )

    # Not-next-to permits the carpet cells themselves; the unique branches
    # additionally allow adjacent cells only when Bob is in the other room.
    assert count_solutions(condition) == expected
