from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from murdoku_checker.domain import (
    AloneWith,
    AnyOf,
    Direction,
    FeatureElement,
    FeatureTargetRelation,
    In,
    InCoordinate,
    Map,
    MurdokuInput,
    NextTo,
    NotNextTo,
    NextToEmptyRoom,
    OtherRoomOccupied,
    RelativePosition,
    RoomRelation,
    RoomRelationKind,
)
from murdoku_checker.domain.rule import Condition
from murdoku_checker.optimization.model import Variables
from murdoku_checker.optimization.positions import (
    in_positions,
    in_coordinate_positions,
    next_to_positions,
    not_next_to_positions,
)


def _needs_rule_constraint(condition: Condition) -> bool:
    if isinstance(condition, AnyOf):
        return any(_needs_rule_constraint(child) for child in condition.conditions)
    return isinstance(
        condition,
        (
            AloneWith,
            NextToEmptyRoom,
            OtherRoomOccupied,
            RelativePosition,
            RoomRelation,
        ),
    ) or (
        isinstance(condition, In) and condition.is_unique
    )


@dataclass(frozen=True, slots=True)
class ConstraintBuilder:
    model: cp_model.CpModel

    def build(self, input_: MurdokuInput, variables: Variables) -> None:
        self.build_person_constraints(input_, variables)
        self.build_row_constraints(variables)
        self.build_column_constraints(variables)
        self.build_rule_constraints(input_, variables)

    def build_person_constraints(
        self, input_: MurdokuInput, variables: Variables
    ) -> None:
        """Each person is in exactly one cell.

        A person left without variables makes the model infeasible.
        """
        people: defaultdict[str, list[cp_model.IntVar]] = defaultdict(list)
        for (name, _, _), variable in variables.items():
            people[name].append(variable)
        for person in input_.people.people:
            self.model.add(sum(people[person.name]) == 1)

    def build_row_constraints(self, variables: Variables) -> None:
        """At most one person can be in each row (same latitude)."""
        rows: defaultdict[int, list[cp_model.IntVar]] = defaultdict(list)
        for (_, latitude, _), variable in variables.items():
            rows[latitude].append(variable)
        for row_variables in rows.values():
            self.model.add(sum(row_variables) <= 1)

    def build_column_constraints(self, variables: Variables) -> None:
        """At most one person can be in each column (same longitude)."""
        columns: defaultdict[int, list[cp_model.IntVar]] = defaultdict(list)
        for (_, _, longitude), variable in variables.items():
            columns[longitude].append(variable)
        for column_variables in columns.values():
            self.model.add(sum(column_variables) <= 1)

    def build_rule_constraints(
        self, input_: MurdokuInput, variables: Variables
    ) -> None:
        """Enforce rules depending on other people, including any_of branches."""
        for rule in input_.rules.rules:
            if _needs_rule_constraint(rule.condition):
                literal = self._condition_literal(
                    rule.person, rule.condition, input_, variables
                )
                self.model.add(literal == 1)

    def _condition_literal(
        self,
        person: str,
        condition: Condition,
        input_: MurdokuInput,
        variables: Variables,
    ) -> cp_model.IntVar:
        """Boolean variable that is true exactly when the condition holds."""
        if isinstance(condition, AnyOf):
            children = [
                self._condition_literal(person, child, input_, variables)
                for child in condition.conditions
            ]
            literal = self.model.new_bool_var("")
            self.model.add_bool_or(children).only_enforce_if(literal)
            self.model.add_bool_and(
                [child.negated() for child in children]
            ).only_enforce_if(literal.negated())
            return literal

        if isinstance(condition, RelativePosition):
            return self._relative_position_literal(
                person, condition, input_.map, variables
            )

        if isinstance(condition, RoomRelation):
            return self._room_relation_literal(
                person, condition, input_.map, variables
            )

        if isinstance(condition, AloneWith):
            return self._alone_with_literal(
                person, condition, input_.map, variables
            )

        if isinstance(condition, NextToEmptyRoom):
            return self._next_to_empty_room_literal(
                person, input_.map, variables
            )

        if isinstance(condition, OtherRoomOccupied):
            return self._other_room_occupied_literal(
                person, condition, input_, variables
            )

        if isinstance(condition, In):
            positions = in_positions(condition, input_.map)
        elif isinstance(condition, InCoordinate):
            positions = in_coordinate_positions(condition, input_.map)
        elif isinstance(condition, NotNextTo):
            positions = not_next_to_positions(condition, input_.map)
        else:
            positions = next_to_positions(condition, input_.map)
        person_in = self._any_of(
            [
                variable
                for (name, *position), variable in variables.items()
                if name == person and tuple(position) in positions
            ]
        )
        if not (isinstance(condition, In) and condition.is_unique):
            return person_in

        crowded = self._any_of(
            [
                variable
                for (name, *position), variable in variables.items()
                if name != person and tuple(position) in positions
            ]
        )
        literal = self.model.new_bool_var("")
        self.model.add_bool_and([person_in, crowded.negated()]).only_enforce_if(literal)
        self.model.add_bool_or([person_in.negated(), crowded]).only_enforce_if(
            literal.negated()
        )
        return literal

    def _relative_position_literal(
        self,
        person: str,
        condition: RelativePosition,
        map_: Map,
        variables: Variables,
    ) -> cp_model.IntVar:
        vertical = condition.direction in (Direction.NORTH, Direction.SOUTH)
        if isinstance(condition.element, FeatureElement):
            if condition.feature_relation is FeatureTargetRelation.IN:
                feature_positions = {
                    (cell.latitude, cell.longitude)
                    for cell in map_.cells
                    if condition.element.value in cell.features
                }
            else:
                feature_positions = next_to_positions(
                    NextTo(element=condition.element), map_
                )
            matches = []
            for (
                candidate,
                latitude,
                longitude,
            ), variable in variables.items():
                if candidate != person:
                    continue
                candidate_coordinate = latitude if vertical else longitude
                for (
                    other,
                    other_latitude,
                    other_longitude,
                ), other_variable in variables.items():
                    if (
                        other == person
                        or (other_latitude, other_longitude) not in feature_positions
                    ):
                        continue
                    other_coordinate = (
                        other_latitude if vertical else other_longitude
                    )
                    difference = candidate_coordinate - other_coordinate
                    if self._matches_relative_difference(difference, condition):
                        matches.append(self._all_of([variable, other_variable]))
            return self._any_of(matches)

        coordinates = {
            name: cp_model.LinearExpr.sum(
                [
                    (latitude if vertical else longitude) * variable
                    for (candidate, latitude, longitude), variable in variables.items()
                    if candidate == name
                ]
            )
            for name in (person, condition.element.value)
        }
        # Exactly-one placement makes each weighted sum the person's coordinate.
        difference = coordinates[person] - coordinates[condition.element.value]
        literal = self.model.new_bool_var("")
        if condition.offset is not None:
            expected = (
                condition.offset
                if condition.direction in (Direction.SOUTH, Direction.EAST)
                else -condition.offset
            )
            self.model.add(difference == expected).only_enforce_if(literal)
            self.model.add(difference != expected).only_enforce_if(
                literal.negated()
            )
            return literal

        if condition.direction in (Direction.SOUTH, Direction.EAST):
            self.model.add(difference > 0).only_enforce_if(literal)
            self.model.add(difference <= 0).only_enforce_if(literal.negated())
        else:
            self.model.add(difference < 0).only_enforce_if(literal)
            self.model.add(difference >= 0).only_enforce_if(literal.negated())
        return literal

    @staticmethod
    def _matches_relative_difference(
        difference: int, condition: RelativePosition
    ) -> bool:
        if condition.offset is not None:
            expected = (
                condition.offset
                if condition.direction in (Direction.SOUTH, Direction.EAST)
                else -condition.offset
            )
            return difference == expected
        if condition.direction in (Direction.SOUTH, Direction.EAST):
            return difference > 0
        return difference < 0

    def _alone_with_literal(
        self,
        person: str,
        condition: AloneWith,
        map_: Map,
        variables: Variables,
    ) -> cp_model.IntVar:
        branches = []
        for room in {cell.room for cell in map_.cells}:
            positions = {
                (cell.latitude, cell.longitude)
                for cell in map_.cells
                if cell.room == room
            }
            person_in = self._person_in_positions(person, positions, variables)
            companion_in = self._person_in_positions(
                condition.element.value, positions, variables
            )
            others_in = self._any_of(
                [
                    variable
                    for (name, latitude, longitude), variable in variables.items()
                    if name not in (person, condition.element.value)
                    and (latitude, longitude) in positions
                ]
            )
            branches.append(
                self._all_of([person_in, companion_in, others_in.negated()])
            )
        return self._any_of(branches)

    def _next_to_empty_room_literal(
        self, person: str, map_: Map, variables: Variables
    ) -> cp_model.IntVar:
        room_positions = {
            room: {
                (cell.latitude, cell.longitude)
                for cell in map_.cells
                if cell.room == room
            }
            for room in {cell.room for cell in map_.cells}
        }
        occupied = {
            room: self._any_of(
                [
                    variable
                    for (_, latitude, longitude), variable in variables.items()
                    if (latitude, longitude) in positions
                ]
            )
            for room, positions in room_positions.items()
        }
        branches = []
        for (name, latitude, longitude), variable in variables.items():
            if name != person:
                continue
            cell = map_.get_cell(latitude, longitude)
            if cell is None:
                continue
            neighbouring_rooms = set()
            for d_latitude, d_longitude in (
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
            ):
                neighbour_latitude = latitude + d_latitude
                neighbour_longitude = longitude + d_longitude
                if neighbour_latitude < 0 or neighbour_longitude < 0:
                    continue
                neighbour = map_.get_cell(
                    neighbour_latitude, neighbour_longitude
                )
                if neighbour is not None and neighbour.room != cell.room:
                    neighbouring_rooms.add(neighbour.room)
            branches.extend(
                self._all_of([variable, occupied[room].negated()])
                for room in neighbouring_rooms
            )
        return self._any_of(branches)

    def _other_room_occupied_literal(
        self,
        person: str,
        condition: OtherRoomOccupied,
        input_: MurdokuInput,
        variables: Variables,
    ) -> cp_model.IntVar:
        eligible = {
            candidate.name
            for candidate in input_.people.people
            if candidate.name != person and candidate.gender is condition.gender
        }
        room_positions = {
            room: {
                (cell.latitude, cell.longitude)
                for cell in input_.map.cells
                if cell.room == room
            }
            for room in condition.rooms
        }
        branches = []
        for own_room, other_room in (
            condition.rooms,
            tuple(reversed(condition.rooms)),
        ):
            own_positions = room_positions[own_room]
            other_positions = room_positions[other_room]
            person_in = self._person_in_positions(
                person, own_positions, variables
            )
            eligible_in_other = self._any_of(
                [
                    variable
                    for (name, latitude, longitude), variable in variables.items()
                    if name in eligible
                    and (latitude, longitude) in other_positions
                ]
            )
            branches.append(self._all_of([person_in, eligible_in_other]))
        return self._any_of(branches)

    def _person_in_positions(
        self, person: str, positions: set[tuple[int, int]], variables: Variables
    ) -> cp_model.IntVar:
        return self._any_of(
            [
                variable
                for (name, latitude, longitude), variable in variables.items()
                if name == person and (latitude, longitude) in positions
            ]
        )

    def _room_relation_literal(
        self,
        person: str,
        condition: RoomRelation,
        map_: Map,
        variables: Variables,
    ) -> cp_model.IntVar:
        room_ids = {
            room: index
            for index, room in enumerate(sorted({cell.room for cell in map_.cells}))
        }
        room_by_position = {
            (cell.latitude, cell.longitude): room_ids[cell.room]
            for cell in map_.cells
        }
        coordinates = {
            name: cp_model.LinearExpr.sum(
                [
                    room_by_position[latitude, longitude] * variable
                    for (candidate, latitude, longitude), variable in variables.items()
                    if candidate == name
                ]
            )
            for name in (person, condition.element.value)
        }
        difference = coordinates[person] - coordinates[condition.element.value]
        literal = self.model.new_bool_var("")
        if condition.relation is RoomRelationKind.SAME:
            self.model.add(difference == 0).only_enforce_if(literal)
            self.model.add(difference != 0).only_enforce_if(literal.negated())
        else:
            self.model.add(difference != 0).only_enforce_if(literal)
            self.model.add(difference == 0).only_enforce_if(literal.negated())
        return literal

    def _any_of(self, operands: list[cp_model.IntVar]) -> cp_model.IntVar:
        """Boolean variable that is true when any operand is true."""
        literal = self.model.new_bool_var("")
        self.model.add_bool_or(operands).only_enforce_if(literal)
        self.model.add_bool_and([o.negated() for o in operands]).only_enforce_if(
            literal.negated()
        )
        return literal

    def _all_of(self, operands: list[cp_model.IntVar]) -> cp_model.IntVar:
        """Boolean variable that is true when every operand is true."""
        literal = self.model.new_bool_var("")
        self.model.add_bool_and(operands).only_enforce_if(literal)
        self.model.add_bool_or([o.negated() for o in operands]).only_enforce_if(
            literal.negated()
        )
        return literal
