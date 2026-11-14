from murdoku_checker.domain import MurdokuInput
from murdoku_checker.apps.solution_checker.model import Placement


def format_solution(input_: MurdokuInput, solution: Placement) -> str:
    """Render a placement with labelled coordinates, people and rooms."""
    cells = input_.map.cells
    if not cells:
        return "First solution: empty map."

    people = {
        person.name: f"P{index}"
        for index, person in enumerate(input_.people.people, start=1)
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
            position, "." if input_.is_cell_occupiable(cell) else "#"
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
        "First solution (rows = latitude, columns = longitude):",
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
    for name, label in people.items():
        latitude, longitude = solution[name]
        lines.append(f"  {label} = {name} (latitude={latitude}, longitude={longitude})")
    lines.extend(f"  {label} = {room}" for room, label in rooms.items())
    return "\n".join(lines)
