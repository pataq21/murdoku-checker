from dataclasses import dataclass
from random import Random

from ortools.sat.python import cp_model

from murdoku_checker.apps.solver_logging import configure_solver_logging
from murdoku_checker.domain.generated_solution import (
    FurniturePlacement,
    GeneratedSolution,
)
from murdoku_checker.domain.generation_specification import GenerationSpecification
from murdoku_checker.domain.grid_cell import GridCell
from murdoku_checker.domain.map import Map
from murdoku_checker.domain.solution import Solution


@dataclass(frozen=True, slots=True)
class _FurnitureOption:
    element: str
    cells: tuple[int, ...]
    selected: cp_model.IntVar


class PlacementModel:
    def __init__(self, specification: GenerationSpecification) -> None:
        self.specification = specification
        config = specification.config
        self.positions = tuple(
            (row, column)
            for row in range(config.rows)
            for column in range(config.columns)
        )
        self.neighbours = [
            [
                other
                for other, (other_row, other_column) in enumerate(self.positions)
                if abs(row - other_row) + abs(column - other_column) == 1
            ]
            for row, column in self.positions
        ]
        self.model = cp_model.CpModel()
        self.room_seeds = self._choose_room_seeds()
        self.room_variables = self._build_rooms()
        self.furniture_options, blocked = self._build_furniture()
        self.person_variables = self._build_people(blocked)
        self._build_victim_constraint()

    def _choose_room_seeds(self) -> tuple[int, ...]:
        random = Random(self.specification.config.seed)
        candidates = list(range(len(self.positions)))
        random.shuffle(candidates)
        seeds = [candidates.pop()]
        distances = [len(self.positions)] * len(self.positions)
        while len(seeds) < self.specification.config.room_count:
            row, column = self.positions[seeds[-1]]
            for cell in candidates:
                other_row, other_column = self.positions[cell]
                distances[cell] = min(
                    distances[cell],
                    abs(row - other_row) + abs(column - other_column),
                )
            seed = max(candidates, key=distances.__getitem__)
            candidates.remove(seed)
            seeds.append(seed)
        return tuple(seeds)

    def _build_rooms(self) -> list[cp_model.IntVar]:
        config = self.specification.config
        size = config.cell_count
        rooms = [
            self.model.new_int_var(0, config.room_count - 1, f"room_{cell}")
            for cell in range(size)
        ]
        depths = [
            self.model.new_int_var(0, size - 1, f"depth_{cell}") for cell in range(size)
        ]
        for room, cell in enumerate(self.room_seeds):
            self.model.add(rooms[cell] == room)
            self.model.add(depths[cell] == 0)

        # Every non-root follows a same-room neighbour of lower depth.
        # Cycles are impossible, so every cell reaches its room's unique root.
        for cell, neighbours in enumerate(self.neighbours):
            if cell in self.room_seeds:
                continue
            parents = []
            for neighbour in neighbours:
                parent = self.model.new_bool_var(f"parent_{cell}_{neighbour}")
                self.model.add(rooms[cell] == rooms[neighbour]).only_enforce_if(parent)
                self.model.add(depths[cell] > depths[neighbour]).only_enforce_if(parent)
                parents.append(parent)
            self.model.add_exactly_one(parents)
        self._build_room_shape_constraints(rooms)
        return rooms

    def _build_room_shape_constraints(self, rooms: list[cp_model.IntVar]) -> None:
        config = self.specification.config
        random = Random(config.seed)
        thin_rooms = []
        placement_costs = []
        self.room_members: list[list[cp_model.IntVar]] = []
        for room in range(config.room_count):
            members = []
            seed_row, seed_column = self.positions[self.room_seeds[room]]
            for cell, variable in enumerate(rooms):
                member = self.model.new_bool_var(f"room_{room}_member_{cell}")
                self.model.add(variable == room).only_enforce_if(member)
                self.model.add(variable != room).only_enforce_if(member.negated())
                members.append(member)
                row, column = self.positions[cell]
                distance = abs(row - seed_row) + abs(column - seed_column)
                placement_costs.append((distance + random.randrange(10)) * member)
            self.room_members.append(members)

            single_axes = []
            extents = []
            for axis, size in enumerate((config.rows, config.columns)):
                coordinates = []
                for coordinate in range(size):
                    used = self.model.new_bool_var(
                        f"room_{room}_axis_{axis}_coordinate_{coordinate}"
                    )
                    line = [
                        member
                        for position, member in zip(self.positions, members)
                        if position[axis] == coordinate
                    ]
                    self.model.add_max_equality(used, line)
                    # A row/column intersects a room in at most one interval.
                    self.model.add_automaton(
                        line,
                        0,
                        [0, 1, 2],
                        [(0, 0, 0), (0, 1, 1), (1, 1, 1), (1, 0, 2), (2, 0, 2)],
                    )
                    coordinates.append(used)
                extent = self.model.new_int_var(1, size, f"room_{room}_extent_{axis}")
                self.model.add(extent == sum(coordinates))
                extents.append(extent)
                single = self.model.new_bool_var(f"room_{room}_single_axis_{axis}")
                self.model.add(extent == 1).only_enforce_if(single)
                self.model.add(extent != 1).only_enforce_if(single.negated())
                single_axes.append(single)

            height, width = extents
            area = self.model.new_int_var(1, config.cell_count, f"room_{room}_area")
            self.model.add(area == sum(members))
            bounding_area = self.model.new_int_var(
                1, config.cell_count, f"room_{room}_bounding_area"
            )
            self.model.add_multiplication_equality(bounding_area, [height, width])
            self.model.add(4 * area >= 3 * bounding_area)
            self.model.add(2 * height <= 3 * width)
            self.model.add(2 * width <= 3 * height)
            thin = self.model.new_bool_var(f"room_{room}_thin")
            self.model.add_max_equality(thin, single_axes)
            thin_rooms.append(thin)
        self.model.add_at_most_one(thin_rooms)
        self.room_placement_cost = cp_model.LinearExpr.sum(placement_costs)

    def _build_furniture(
        self,
    ) -> tuple[list[_FurnitureOption], list[cp_model.IntVar]]:
        size = len(self.positions)
        coverage: list[list[cp_model.IntVar]] = [[] for _ in range(size)]
        blocking: list[list[cp_model.IntVar]] = [[] for _ in range(size)]
        options: list[_FurnitureOption] = []
        for item in self.specification.elements:
            footprints = (
                [(cell,) for cell in range(size)]
                if item.size == 1
                else [
                    (cell, neighbour)
                    for cell, neighbours in enumerate(self.neighbours)
                    for neighbour in neighbours
                    if cell < neighbour
                ]
            )
            for instance in range(item.count):
                choices = []
                for index, cells in enumerate(footprints):
                    selected = self.model.new_bool_var(
                        f"furniture_{item.element.name}_{instance}_{index}"
                    )
                    choices.append(selected)
                    options.append(_FurnitureOption(item.element.name, cells, selected))
                    if len(cells) == 2:
                        self.model.add(
                            self.room_variables[cells[0]]
                            == self.room_variables[cells[1]]
                        ).only_enforce_if(selected)
                    for cell in cells:
                        coverage[cell].append(selected)
                        if not item.element.is_occupiable:
                            blocking[cell].append(selected)
                self.model.add_exactly_one(choices)

        blocked = []
        for cell in range(size):
            self.model.add_at_most_one(coverage[cell])
            variable = self.model.new_bool_var(f"blocked_{cell}")
            self.model.add(variable == sum(blocking[cell]))
            blocked.append(variable)
        furnished_rooms = []
        if options:
            occupied = []
            for cell in range(size):
                variable = self.model.new_bool_var(f"furnished_cell_{cell}")
                self.model.add(variable == sum(coverage[cell]))
                occupied.append(variable)
            for room, members in enumerate(self.room_members):
                furniture_in_room = []
                for cell, member in enumerate(members):
                    present = self.model.new_bool_var(
                        f"furniture_in_room_{room}_{cell}"
                    )
                    self.model.add_min_equality(present, [member, occupied[cell]])
                    furniture_in_room.append(present)
                furnished = self.model.new_bool_var(f"furnished_room_{room}")
                self.model.add_max_equality(furnished, furniture_in_room)
                furnished_rooms.append(furnished)
        config = self.specification.config
        # One more furnished room outweighs any improvement in room placement.
        furniture_weight = size * (10 * (config.rows + config.columns - 2) + 9) + 1
        self.model.minimize(
            self.room_placement_cost - furniture_weight * sum(furnished_rooms)
        )
        return options, blocked

    def _build_people(self, blocked: list[cp_model.IntVar]) -> list[cp_model.IntVar]:
        config = self.specification.config
        rows = []
        columns = []
        positions = []
        for person in range(config.person_count):
            row = self.model.new_int_var(0, config.rows - 1, f"person_row_{person}")
            column = self.model.new_int_var(
                0, config.columns - 1, f"person_column_{person}"
            )
            position = self.model.new_int_var(
                0, config.cell_count - 1, f"person_position_{person}"
            )
            self.model.add(position == row * config.columns + column)
            self.model.add_element(position, blocked, 0)
            rows.append(row)
            columns.append(column)
            positions.append(position)
        self.model.add_all_different(rows)
        self.model.add_all_different(columns)
        return positions

    def _build_victim_constraint(self) -> None:
        person_rooms = []
        for person, position in enumerate(self.person_variables):
            room = self.model.new_int_var(
                0, self.specification.config.room_count - 1, f"person_room_{person}"
            )
            self.model.add_element(position, self.room_variables, room)
            person_rooms.append(room)

        victim_room = person_rooms[-1]
        companions = []
        for person, room in enumerate(person_rooms[:-1]):
            companion = self.model.new_bool_var(f"victim_companion_{person}")
            self.model.add(room == victim_room).only_enforce_if(companion)
            self.model.add(room != victim_room).only_enforce_if(companion.negated())
            companions.append(companion)
        self.model.add_exactly_one(companions)

    def solve(self, *, solver_logs: bool = False) -> GeneratedSolution | None:
        solver = cp_model.CpSolver()
        configure_solver_logging(solver, solver_logs)
        solver.parameters.num_search_workers = 8
        solver.parameters.random_seed = Random(
            self.specification.config.seed
        ).randrange(2**31)
        solver.parameters.randomize_search = True
        solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
        solver.parameters.max_time_in_seconds = 10
        status = solver.solve(self.model)
        if status == cp_model.INFEASIBLE:
            return None
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(
                f"Generator ended without a conclusive result: "
                f"{solver.status_name(status)}"
            )

        features: list[list[str]] = [[] for _ in self.positions]
        furniture = []
        for option in self.furniture_options:
            if solver.boolean_value(option.selected):
                furniture.append(
                    FurniturePlacement(
                        element=option.element,
                        cells=tuple(self.positions[cell] for cell in option.cells),
                    )
                )
                for cell in option.cells:
                    features[cell].append(option.element)
        map_ = Map(
            cells=tuple(
                GridCell(
                    latitude=row,
                    longitude=column,
                    room=f"room_{solver.value(self.room_variables[cell]) + 1}",
                    features=tuple(features[cell]),
                )
                for cell, (row, column) in enumerate(self.positions)
            )
        )
        config = self.specification.config
        person_names = (
            config.person_names
            if config.person_names is not None
            else tuple(f"person_{index + 1}" for index in range(config.person_count))
        )
        solution = Solution(
            map=map_,
            placements={
                name: self.positions[solver.value(variable)]
                for name, variable in zip(
                    person_names, self.person_variables, strict=True
                )
            },
        )
        return GeneratedSolution(
            specification=self.specification,
            solution=solution,
            victim=person_names[-1],
            furniture=tuple(furniture),
        )
