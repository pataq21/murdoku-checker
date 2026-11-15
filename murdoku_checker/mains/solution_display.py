from collections.abc import Sequence

from murdoku_checker.apps.solution_checker.model import Placement
from murdoku_checker.domain import GeneratedSolution, Map, MurdokuInput, Position


def format_solution(input_: MurdokuInput, solution: Placement) -> str:
    """Render a placement with labelled coordinates, people and rooms."""
    return _format_placement(
        input_.map,
        solution,
        tuple(person.name for person in input_.people.people),
        frozenset(
            cell.position
            for cell in input_.map.cells
            if not input_.is_cell_occupiable(cell)
        ),
        "First solution",
    )


def format_generated_solution(generated: GeneratedSolution) -> str:
    """Render a generated board without inventing person attributes."""
    blocked_elements = {
        item.element.name
        for item in generated.specification.elements
        if not item.element.is_occupiable
    }
    solution = generated.solution
    return _format_placement(
        solution.map,
        solution.placements,
        tuple(solution.placements),
        frozenset(
            cell.position
            for cell in solution.map.cells
            if blocked_elements.intersection(cell.features)
        ),
        "Generated solution",
        victim=generated.victim,
    )


def _format_placement(
    map_: Map,
    solution: Placement,
    person_names: Sequence[str],
    blocked_positions: frozenset[Position],
    title: str,
    *,
    victim: str | None = None,
) -> str:
    cells = map_.cells
    if not cells:
        return f"{title}: empty map."

    people = {
        name: f"P{index}" + ("*" if name == victim else "")
        for index, name in enumerate(person_names, start=1)
    }
    rooms = {
        room: f"R{index}"
        for index, room in enumerate(sorted({cell.room for cell in cells}), start=1)
    }
    occupants = {solution[name]: label for name, label in people.items()}
    tokens = {}
    for cell in cells:
        position = (cell.latitude, cell.longitude)
        marker = occupants.get(
            position, "#" if position in blocked_positions else "."
        )
        tokens[position] = f"{marker}/{rooms[cell.room]}"

    latitudes = sorted({cell.latitude for cell in cells})
    longitudes = sorted({cell.longitude for cell in cells})
    width = max(
        max(len(token) for token in tokens.values()),
        max(len(str(longitude)) for longitude in longitudes),
    )
    row_width = len(str(latitudes[-1]))
    lines = [
        f"{title} (rows = latitude, columns = longitude):",
        " " * (row_width + 3)
        + "   ".join(f"{longitude:^{width}}" for longitude in longitudes).rstrip(),
    ]
    for latitude in latitudes:
        row = " | ".join(
            f"{tokens.get((latitude, longitude), ''):^{width}}"
            for longitude in longitudes
        )
        lines.append(f"{latitude:>{row_width}} | {row} |")

    lines.extend(
        [
            "",
            "Legend:",
            "  . = unoccupied cell; # = blocked cell; blank = no cell",
        ]
    )
    if victim is not None:
        lines.append("  * = victim")
    for name, label in people.items():
        latitude, longitude = solution[name]
        role = " (victim)" if name == victim else ""
        lines.append(
            f"  {label} = {name}{role} (latitude={latitude}, longitude={longitude})"
        )
    lines.extend(f"  {label} = {room}" for room, label in rooms.items())
    return "\n".join(lines)
