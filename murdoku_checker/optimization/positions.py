from murdoku_checker.domain import Cell, In, Map, NextTo, RoomElement

Position = tuple[int, int]

_NEIGHBOUR_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def in_positions(condition: In, map_: Map) -> frozenset[Position]:
    """Cells of the room, or cells holding the feature."""
    element = condition.element
    if isinstance(element, RoomElement):
        matches = (cell for cell in map_.cells if cell.room == element.value)
    else:
        matches = (cell for cell in map_.cells if element.value in cell.features)
    return frozenset((cell.latitude, cell.longitude) for cell in matches)


def next_to_positions(condition: NextTo, map_: Map) -> frozenset[Position]:
    """Cells at Manhattan distance 1 from the feature, in the same room."""
    positions: set[Position] = set()
    for cell in map_.cells:
        if condition.element.value not in cell.features:
            continue
        for d_latitude, d_longitude in _NEIGHBOUR_OFFSETS:
            latitude = cell.latitude + d_latitude
            longitude = cell.longitude + d_longitude
            if latitude < 0 or longitude < 0:
                continue
            neighbour: Cell | None = map_.get_cell(latitude, longitude)
            if neighbour is not None and neighbour.room == cell.room:
                positions.add((latitude, longitude))
    return frozenset(positions)
