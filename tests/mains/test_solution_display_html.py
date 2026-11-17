from html import escape
from html.parser import HTMLParser

from murdoku_checker.domain import (
    AnyOfRule,
    CoordinateAxis,
    Element,
    ElementSpecification,
    FurniturePlacement,
    GeneratedSolution,
    GenerationConfig,
    GenerationSpecification,
    GridCell,
    InCoordinateRule,
    Map,
    Rules,
    Solution,
)
from murdoku_checker.mains.solution_display_html import format_solution_html


class ParsedHTML(HTMLParser):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.feed(content)

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.tags.append((tag, dict(attrs)))

    def with_class(self, class_name: str) -> list[dict[str, str | None]]:
        return [
            attrs
            for _, attrs in self.tags
            if class_name in (attrs.get("class") or "").split()
        ]


def sample_solution(
    room_name: str = "Kitchen",
    element_name: str = "Table",
    person_name: str = "Alice",
) -> GeneratedSolution:
    furniture = (
        FurniturePlacement(element_name, ((0, 0), (0, 1))),
        FurniturePlacement("Wardrobe", ((0, 2), (1, 2))),
        FurniturePlacement("Chair", ((1, 0),)),
    )
    features = {
        position: item.element for item in furniture for position in item.cells
    }
    return GeneratedSolution(
        specification=GenerationSpecification(
            config=GenerationConfig(
                rows=2,
                columns=3,
                element_coverage_percent=83,
                element_type_count=3,
                room_count=2,
                seed=17,
            ),
            elements=(
                ElementSpecification(
                    Element(name=element_name, is_occupiable=True), 2, 1
                ),
                ElementSpecification(Element(name="Wardrobe"), 2, 1),
                ElementSpecification(
                    Element(name="Chair", is_occupiable=True), 1, 1
                ),
            ),
        ),
        solution=Solution(
            map=Map(
                cells=tuple(
                    GridCell(
                        latitude=row,
                        longitude=column,
                        room=room_name if column < 2 else "Hall",
                        features=(
                            (features[(row, column)],)
                            if (row, column) in features
                            else ()
                        ),
                    )
                    for row in range(2)
                    for column in range(3)
                )
            ),
            placements={person_name: (0, 0), "Bob": (1, 1)},
        ),
        victim="Bob",
        furniture=furniture,
    )


def test_html_places_furniture_spans_people_and_room_walls() -> None:
    document = ParsedHTML(format_solution_html(sample_solution()))

    cells = {
        (cell["data-row"], cell["data-column"]): cell
        for cell in document.with_class("cell")
    }
    assert len(cells) == 6
    assert "wall-east" not in (cells[("0", "0")]["class"] or "")
    assert "wall-east" in (cells[("0", "1")]["class"] or "")
    assert "wall-west" in (cells[("0", "2")]["class"] or "")
    assert "wall-south" in (cells[("1", "1")]["class"] or "")

    furniture = document.with_class("furniture")
    assert len(furniture) == 3
    assert furniture[0]["style"] == "grid-row: 2 / span 1; grid-column: 2 / span 2;"
    assert furniture[1]["style"] == "grid-row: 2 / span 2; grid-column: 4 / span 1;"
    assert furniture[2]["style"] == "grid-row: 3 / span 1; grid-column: 2 / span 1;"
    assert furniture[0]["class"] == "furniture walkable"
    assert furniture[1]["class"] == "furniture blocked"

    people = document.with_class("person")
    assert len(people) == 2
    assert people[0]["style"] == "grid-row: 2; grid-column: 2;"
    assert people[1]["style"] == "grid-row: 3; grid-column: 3;"
    assert people[0]["aria-label"] == "P1: Alice / row 0, column 0"
    assert people[0]["class"] == "person"
    assert people[1]["class"] == "person victim"
    assert people[1]["aria-label"] == "P2: Bob (victim) / row 1, column 1"
    assert len([
        person for person in people if "victim" in (person["class"] or "").split()
    ]) == 1


def test_html_escapes_names_in_text_attributes_and_legends() -> None:
    name = '</style><script>alert("x")</script><b onmouseover="bad"> &'
    content = format_solution_html(sample_solution(name, name, name))
    document = ParsedHTML(content)

    assert escape(name) in content
    assert name not in content
    assert not any(tag in ("script", "b") for tag, _ in document.tags)
    assert not any(
        attribute.startswith("on")
        for _, attributes in document.tags
        for attribute in attributes
    )
    assert document.with_class("furniture")[0]["data-element"] == name


def test_html_is_standalone_and_handles_a_board_without_furniture() -> None:
    generated = GeneratedSolution(
        specification=GenerationSpecification(
            config=GenerationConfig(
                rows=2, columns=2, element_coverage_percent=0,
                element_type_count=0, room_count=1,
            ),
            elements=(),
        ),
        solution=Solution(
            map=Map(
                cells=tuple(
                    GridCell(latitude=row, longitude=column, room="Room")
                    for row in range(2)
                    for column in range(2)
                )
            ),
            placements={"Alice": (0, 0), "Bob": (1, 1)},
        ),
        victim="Bob",
        furniture=(),
    )
    content = format_solution_html(generated)
    document = ParsedHTML(content)

    assert content.startswith("<!doctype html>")
    assert "No furniture on this board." in content
    assert len(document.with_class("cell")) == 4
    assert len(document.with_class("person")) == 2
    assert document.with_class("furniture") == []
    assert not any(tag in ("script", "link", "iframe") for tag, _ in document.tags)
    assert not any("src" in attrs for _, attrs in document.tags)
    assert any(
        tag == "meta" and attrs.get("name") == "viewport"
        for tag, attrs in document.tags
    )
    assert document.with_class("clues") == []


def test_html_shows_selected_clues_in_order_and_escapes_descriptions() -> None:
    name = '<script>alert("clue")</script> & Alice'
    row = InCoordinateRule(person=name, axis=CoordinateAxis.ROW, value=0)
    column = InCoordinateRule(person=name, axis=CoordinateAxis.COLUMN, value=0)
    disjunction = AnyOfRule(person=name, conditions=(row, column))
    rules = Rules(rules=(row, disjunction))
    content = format_solution_html(sample_solution(person_name=name), rules=rules)
    document = ParsedHTML(content)

    assert len(document.with_class("clues")) == 1
    assert (
        f"<ol><li>{escape(row.description)}</li>"
        f"<li>{escape(disjunction.description)}</li></ol>"
    ) in content
    assert "2 clue(s)" in content
    assert "clues and uniqueness are not evaluated here" not in content
    assert not any(tag == "script" for tag, _ in document.tags)


def test_html_handles_a_puzzle_without_selected_clues() -> None:
    content = format_solution_html(sample_solution(), rules=Rules())
    assert len(ParsedHTML(content).with_class("clues")) == 1
    assert "No clues required." in content


def test_puzzle_html_omits_people_positions_but_keeps_map_names_and_clues() -> None:
    name = '<script>alert("person")</script> & Alice'
    generated = sample_solution(person_name=name)
    rule = InCoordinateRule(person=name, axis=CoordinateAxis.ROW, value=0)
    rules = Rules(rules=(rule,))
    solution = ParsedHTML(format_solution_html(generated, rules=rules))
    content = format_solution_html(generated, rules=rules, show_solution=False)
    puzzle = ParsedHTML(content)

    assert puzzle.with_class("person") == []
    assert puzzle.with_class("person-badge") == solution.with_class("person-badge")
    assert puzzle.with_class("cell") == solution.with_class("cell")
    assert puzzle.with_class("furniture") == solution.with_class("furniture")
    assert escape(name) in content
    assert "Bob (victim)" in content
    assert f"<li>{escape(rule.description)}</li>" in content
    assert "<small>Row " not in content
    assert not any(
        "P1:" in (attrs.get("title") or "") or "P2:" in (attrs.get("title") or "")
        for _, attrs in puzzle.tags
    )
    assert "<title>Murdoku - Generated puzzle</title>" in content
    assert not any(tag in ("script", "link", "iframe") for tag, _ in puzzle.tags)
