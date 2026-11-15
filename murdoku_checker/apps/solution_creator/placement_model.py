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
        self.room_variables = self._build_rooms()
        self.furniture_options, blocked = self._build_furniture()
        self.person_variables = self._build_people(blocked)
        self._build_victim_constraint()

    def _build_rooms(self) -> list[cp_model.IntVar]:
        config = self.specification.config
        size = config.cell_count
        rooms = [
            self.model.new_int_var(0, config.room_count - 1, f"room_{cell}")
            for cell in range(size)
        ]
        depths = [
            self.model.new_int_var(0, size - 1, f"depth_{cell}")
            for cell in range(size)
        ]
        roots_by_cell: list[list[cp_model.IntVar]] = [[] for _ in range(size)]
        for room in range(config.room_count):
            roots = []
            for cell in range(size):
                root = self.model.new_bool_var(f"root_{room}_{cell}")
                roots.append(root)
                roots_by_cell[cell].append(root)
                self.model.add(rooms[cell] == room).only_enforce_if(root)
                self.model.add(depths[cell] == 0).only_enforce_if(root)
            self.model.add_exactly_one(roots)

        # Every non-root follows a same-room neighbour of lower depth.
        # Cycles are impossible, so every cell reaches its room's unique root.
        for cell, neighbours in enumerate(self.neighbours):
            parents = []
            for neighbour in neighbours:
                parent = self.model.new_bool_var(f"parent_{cell}_{neighbour}")
                self.model.add(rooms[cell] == rooms[neighbour]).only_enforce_if(
                    parent
                )
                self.model.add(depths[cell] > depths[neighbour]).only_enforce_if(
                    parent
                )
                parents.append(parent)
            self.model.add_exactly_one([*roots_by_cell[cell], *parents])
        return rooms

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
                    options.append(
                        _FurnitureOption(item.element.name, cells, selected)
                    )
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
        return options, blocked

    def _build_people(
        self, blocked: list[cp_model.IntVar]
    ) -> list[cp_model.IntVar]:
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
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = Random(
            self.specification.config.seed
        ).randrange(2**31)
        solver.parameters.randomize_search = True
        solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
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
        solution = Solution(
            map=map_,
            placements={
                f"person_{person + 1}": self.positions[solver.value(variable)]
                for person, variable in enumerate(self.person_variables)
            },
        )
        return GeneratedSolution(
            specification=self.specification,
            solution=solution,
            victim=f"person_{self.specification.config.person_count}",
            furniture=tuple(furniture),
        )
