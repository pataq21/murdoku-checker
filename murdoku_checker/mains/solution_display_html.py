from html import escape

from murdoku_checker.domain import GeneratedSolution


_STYLES = """
:root { color-scheme: light; font-family: "Segoe UI", system-ui, sans-serif;
  color: #243437; background: #f4f3ee; }
* { box-sizing: border-box; }
body { margin: 0; }
main { max-width: 1220px; margin: auto; padding: 48px 28px; }
.eyebrow { font-size: 12px; letter-spacing: .18em; font-weight: 700; color: #52665f; }
h1 { font-size: clamp(30px, 5vw, 46px); letter-spacing: -.045em; margin: 12px 0; }
.intro { color: #5b6867; margin: 0; line-height: 1.6; }
.stats { display: flex; flex-wrap: wrap; gap: 8px; margin: 24px 0 30px; }
.stat { background: white; border: 1px solid #dedfd7; border-radius: 8px;
  padding: 9px 13px; font-size: 13px; }
.stat strong { margin-right: 5px; }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px;
  gap: 22px; align-items: start; }
.panel { background: #fff; border: 1px solid #dedfd7; border-radius: 16px;
  box-shadow: 0 6px 24px #24343706; overflow: hidden; }
.panel-heading { display: flex; justify-content: space-between; gap: 16px;
  align-items: baseline; padding: 20px 24px; border-bottom: 1px solid #eeeee8; }
h2 { font-size: 16px; margin: 0; }
.panel-heading span, .muted { color: #667571; font-size: 12px; }
.board-scroll { padding: 24px; overflow: auto; }
.board { --cell-size: 108px; display: grid; width: max-content; margin: auto;
  grid-template-columns: 28px repeat(var(--columns), var(--cell-size));
  grid-template-rows: 28px repeat(var(--rows), var(--cell-size)); isolation: isolate; }
.axis { display: grid; place-items: center; color: #6b7770;
  font-size: 12px; font-variant-numeric: tabular-nums; }
.cell { position: relative; background: var(--room-fill); z-index: 1;
  border: 1px solid #24343712; }
.wall-north { border-top: 3px solid var(--room-edge); }
.wall-south { border-bottom: 3px solid var(--room-edge); }
.wall-west { border-left: 3px solid var(--room-edge); }
.wall-east { border-right: 3px solid var(--room-edge); }
.room-label { position: absolute; top: 4px; left: 7px; color: #40504c;
  font-size: 10px; font-weight: 700; letter-spacing: .05em; }
.furniture { z-index: 2; min-width: 0; margin: 24px 9px 9px; border-radius: 9px;
  padding: 6px 8px; border: 2px solid #6e9690; background: #e0eee9;
  color: #28524a; font-size: 12px; font-weight: 700; }
.furniture.blocked { color: #695643; border: 2px dashed #9d8c74;
  background: repeating-linear-gradient(135deg, #eee7db 0 6px, #e7dfd1 6px 12px); }
.person { z-index: 3; align-self: end; justify-self: end; margin: 9px;
  display: grid; place-items: center; min-width: 36px; height: 36px;
  padding: 0 6px; border-radius: 50%; border: 2px solid white;
  background: #263e48; color: white; font-size: 12px; font-weight: 700;
  box-shadow: 0 2px 6px #172b4033; }
.board-key { display: flex; flex-wrap: wrap; gap: 16px; padding: 16px 24px;
  border-top: 1px solid #eeeee8; font-size: 12px; color: #586862; }
.key { display: flex; align-items: center; gap: 7px; }
.swatch { width: 15px; height: 15px; border-radius: 4px; flex-shrink: 0;
  background: var(--room-fill, #e0eee9); border: 1px solid var(--room-edge, #6e9690); }
.swatch.blocked { background: #e7dfd1; border: 2px dashed #9d8c74; }
.sidebar { display: grid; gap: 16px; }
.legend { padding: 20px; }
.legend h2 { margin-bottom: 16px; }
.legend ul { padding: 0; margin: 0; list-style: none; display: grid; gap: 14px; }
.legend li { display: flex; align-items: flex-start; gap: 10px; font-size: 13px; }
.legend li > div { min-width: 0; overflow-wrap: anywhere; }
.legend small { display: block; color: #667571; margin-top: 4px; line-height: 1.4; }
.badge { background: #edf0eb; padding: 4px 6px; border-radius: 5px;
  font-weight: 700; font-size: 11px; flex-shrink: 0; }
.person-badge { background: #263e48; color: white; }
.person.victim, .person-badge.victim { background: #8b3449; }
footer { color: #667571; font-size: 12px; margin-top: 24px; line-height: 1.6; }
@media (max-width: 800px) {
  main { padding: 24px 12px; }
  .layout { grid-template-columns: 1fr; }
  .sidebar { grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }
  .board-scroll { padding: 16px; }
  .board { --cell-size: 92px; }
}
@media print {
  body { background: white; }
  main { padding: 0; }
  .layout { display: block; }
  .sidebar { margin-top: 16px; grid-template-columns: repeat(3, 1fr); }
  .board-scroll { overflow: visible; }
}
"""


def _room_style(index: int) -> str:
    hue = (index * 137 + 35) % 360
    return (
        f"--room-fill: hsl({hue} 42% 89%); "
        f"--room-edge: hsl({hue} 24% 43%);"
    )


def format_solution_html(generated: GeneratedSolution) -> str:
    """Render a self-contained, static HTML map with individual furniture."""
    solution = generated.solution
    config = generated.specification.config
    rooms = solution.map.rooms
    room_indices = {room.name: index for index, room in enumerate(rooms)}
    types = {
        item.element.name: item for item in generated.specification.elements
    }
    board = []
    for column in range(config.columns):
        board.append(
            f'<div class="axis" style="grid-row: 1; grid-column: {column + 2};">'
            f"{column}</div>"
        )
    for row in range(config.rows):
        board.append(
            f'<div class="axis" style="grid-row: {row + 2}; grid-column: 1;">'
            f"{row}</div>"
        )
    for cell in solution.map.cells:
        row, column = cell.position
        walls = []
        for side, dr, dc in (
            ("north", -1, 0), ("south", 1, 0),
            ("west", 0, -1), ("east", 0, 1),
        ):
            neighbour = (
                solution.map.get_cell(row + dr, column + dc)
                if row + dr >= 0 and column + dc >= 0
                else None
            )
            if neighbour is None or neighbour.room != cell.room:
                walls.append(f"wall-{side}")
        index = room_indices[cell.room]
        label = escape(f"{cell.room} / row {row}, column {column}")
        board.append(
            f'<div class="cell {" ".join(walls)}" data-row="{row}" '
            f'data-column="{column}" title="{label}" aria-label="{label}" '
            f'style="grid-row: {row + 2}; grid-column: {column + 2}; '
            f'{_room_style(index)}">'
            f'<span class="room-label">R{index + 1}</span></div>'
        )

    furniture_legend = []
    for index, item in enumerate(generated.furniture, start=1):
        element = types[item.element].element
        row = min(position[0] for position in item.cells)
        column = min(position[1] for position in item.cells)
        row_span = max(position[0] for position in item.cells) - row + 1
        column_span = max(position[1] for position in item.cells) - column + 1
        state = "Walkable" if element.is_occupiable else "Blocked"
        label = escape(f"F{index}: {item.element} / {state}")
        kind = "walkable" if element.is_occupiable else "blocked"
        board.append(
            f'<div class="furniture {kind}" data-element="{escape(item.element)}" '
            f'title="{label}" aria-label="{label}" '
            f'style="grid-row: {row + 2} / span {row_span}; '
            f'grid-column: {column + 2} / span {column_span};">F{index}</div>'
        )
        coordinates = ", ".join(f"({r}, {c})" for r, c in item.cells)
        furniture_legend.append(
            f'<li><span class="badge">F{index}</span><div>{escape(item.element)}'
            f"<small>{state} / {len(item.cells)} cell(s)<br>{coordinates}"
            "</small></div></li>"
        )

    people_legend = []
    for index, (name, (row, column)) in enumerate(
        solution.placements.items(), start=1
    ):
        is_victim = name == generated.victim
        role = " (victim)" if is_victim else ""
        marker = f"P{index}" + ("*" if is_victim else "")
        kind = " victim" if is_victim else ""
        label = escape(f"P{index}: {name}{role} / row {row}, column {column}")
        board.append(
            f'<div class="person{kind}" title="{label}" aria-label="{label}" '
            f'style="grid-row: {row + 2}; grid-column: {column + 2};">{marker}</div>'
        )
        people_legend.append(
            f'<li><span class="badge person-badge{kind}">{marker}</span>'
            f"<div>{escape(name)}{role}<small>Row {row} / Column {column}"
            "</small></div></li>"
        )

    room_legend = [
        f'<li><span class="swatch" style="{_room_style(index)}"></span>'
        f"<div><strong>R{index + 1}</strong> / {escape(room.name)}"
        f"<small>{len(room.cells)} cell(s)</small></div></li>"
        for index, room in enumerate(rooms)
    ]
    seed = str(config.seed) if config.seed is not None else "Random"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Murdoku - Generated solution</title>
<style>{_STYLES}</style>
</head>
<body>
<main>
  <header>
    <div class="eyebrow">MURDOKU / SOLUTION CREATOR</div>
    <h1>Your generated board.</h1>
    <p class="intro">A connected map, furnished rooms and a place for every person.</p>
    <div class="stats">
      <span class="stat"><strong>{config.rows} x {config.columns}</strong> grid</span>
      <span class="stat"><strong>{len(rooms)}</strong> rooms</span>
      <span class="stat"><strong>{len(solution.placements)}</strong> people</span>
      <span class="stat"><strong>{config.element_cell_count}</strong> furniture cells</span>
      <span class="stat">Seed <strong>{seed}</strong></span>
    </div>
  </header>
  <div class="layout">
    <section class="panel" aria-labelledby="map-heading">
      <div class="panel-heading">
        <h2 id="map-heading">The board</h2><span>Coordinates start at 0</span>
      </div>
      <div class="board-scroll" tabindex="0" role="region" aria-label="Scrollable board">
        <div class="board" role="group" aria-label="Generated map"
             style="--rows: {config.rows}; --columns: {config.columns};">
          {"".join(board)}
        </div>
      </div>
      <div class="board-key">
        <span class="key"><span class="badge person-badge">P</span> Person</span>
        <span class="key"><span class="badge person-badge victim">P*</span> Victim</span>
        <span class="key"><span class="swatch"></span> Walkable furniture</span>
        <span class="key"><span class="swatch blocked"></span> Blocked furniture</span>
      </div>
    </section>
    <aside class="sidebar" aria-label="Map legend">
      <section class="panel legend">
        <h2>Rooms</h2><ul>{"".join(room_legend)}</ul>
      </section>
      <section class="panel legend">
        <h2>People</h2><ul>{"".join(people_legend)}</ul>
      </section>
      <section class="panel legend">
        <h2>Furniture</h2>
        {"<ul>" + "".join(furniture_legend) + "</ul>" if furniture_legend else '<p class="muted">No furniture on this board.</p>'}
      </section>
    </aside>
  </div>
  <footer>
    Each furniture label identifies one instance, including pieces spanning two cells.
    Thick borders separate rooms. People may stand on walkable furniture.<br>
    The last person is the victim and shares a room with exactly one other person.<br>
    Generated target solution / clues and uniqueness are not evaluated here.
    This file works offline.
  </footer>
</main>
</body>
</html>
"""
