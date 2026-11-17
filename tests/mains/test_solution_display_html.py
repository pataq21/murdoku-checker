from base64 import b64decode
from html import escape
from html.parser import HTMLParser
from importlib.resources import files

import pytest

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
    victim_name: str = "Bob",
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
            placements={person_name: (0, 0), victim_name: (1, 1)},
        ),
        victim=victim_name,
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


@pytest.mark.parametrize("show_solution", [True, False])
def test_html_labels_furniture_directly_without_a_furniture_legend(
    show_solution: bool,
) -> None:
    content = format_solution_html(sample_solution(), show_solution=show_solution)
    furniture = ParsedHTML(content).with_class("furniture")

    for item, label in zip(
        furniture,
        ("Table", "Wardrobe", "Chair"),
        strict=True,
    ):
        assert item["title"] == label
        assert item["aria-label"] == label
        assert f';">{label}</div>' in content
    assert "F1" not in content
    assert "F2" not in content
    assert "F3" not in content
    assert "<h2>Furniture</h2>" not in content


@pytest.mark.parametrize("show_solution", [True, False])
@pytest.mark.parametrize(
    ("element_name", "filename"),
    [
        ("Chuso", "chuso.png"),
        ("Montse", "montse.png"),
        ("chuso", None),
        ("montse", None),
        ("Table", None),
    ],
)
def test_html_embeds_element_image_only_for_exact_element_name(
    show_solution: bool, element_name: str, filename: str | None,
) -> None:
    content = format_solution_html(
        sample_solution(element_name=element_name), show_solution=show_solution,
    )
    document = ParsedHTML(content)
    images = document.with_class("furniture-image")

    if filename is None:
        assert images == []
        assert document.with_class("with-image") == []
        return

    assert len(images) == 1
    assert images[0]["alt"] == element_name
    source = images[0]["src"]
    assert source is not None
    prefix, data = source.split(",", 1)
    assert prefix == "data:image/png;base64"
    assert b64decode(data, validate=True) == (
        files("murdoku_checker").joinpath("assets", filename).read_bytes()
    )
    furniture = document.with_class("with-image")
    assert len(furniture) == 1
    assert furniture[0]["data-element"] == element_name
    assert furniture[0]["style"] == "grid-row: 2 / span 1; grid-column: 2 / span 2;"
    assert "hidden" not in furniture[0]
    assert "hidden" not in images[0]
    assert f'<span class="furniture-label">{element_name}</span>' in content


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
    assert f';">{escape(name)}</div>' in content


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
    assert "<h2>Furniture</h2>" not in content
    assert "No furniture on this board." not in content
    assert len(document.with_class("cell")) == 4
    assert len(document.with_class("person")) == 2
    assert document.with_class("furniture") == []
    assert not any(tag in ("script", "link", "iframe") for tag, _ in document.tags)
    assert not any("src" in attrs for _, attrs in document.tags)
    assert any(
        tag == "meta" and attrs.get("name") == "viewport"
        for tag, attrs in document.tags
    )
    assert len(document.with_class("clues")) == 1


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
        "<ol><li>Bob is the victim. It was alone with someone</li>"
        f"<li>{escape(row.description)}</li>"
        f"<li>{escape(disjunction.description)}</li></ol>"
    ) in content
    assert "3 clue(s)" in content
    assert f"<li>{escape(name)} is in row 0.</li>" in content
    assert (
        f"<li>Either {escape(name)} is in row 0 or "
        f"{escape(name)} is in column 0.</li>"
    ) in content
    assert "clues and uniqueness are not evaluated here" not in content
    assert not any(tag == "script" for tag, _ in document.tags)


@pytest.mark.parametrize("show_solution", [True, False])
@pytest.mark.parametrize("rules", [None, Rules()])
def test_html_always_includes_the_escaped_victim_clue(
    show_solution: bool, rules: Rules | None,
) -> None:
    victim = '<script>alert("victim")</script> & Bob'
    content = format_solution_html(
        sample_solution(victim_name=victim),
        rules=rules,
        show_solution=show_solution,
    )
    assert len(ParsedHTML(content).with_class("clues")) == 1
    assert (
        f"<ol><li>{escape(victim)} is the victim. It was alone with someone</li></ol>"
    ) in content
    assert "1 clue(s)" in content
    assert "No clues required." not in content
    assert victim not in content


@pytest.mark.parametrize("show_solution", [True, False])
@pytest.mark.parametrize("rules", [None, Rules()])
def test_html_places_clues_before_board_and_legends_below_it(
    show_solution: bool, rules: Rules | None,
) -> None:
    content = format_solution_html(
        sample_solution(), rules=rules, show_solution=show_solution,
    )
    document = ParsedHTML(content)
    board_column = content.index('<div class="board-column">')
    board = content.index('aria-labelledby="map-heading"')
    legends = content.index('<aside class="legends"')

    assert board_column < board < legends
    assert content.index("<h2>Rooms</h2>") > legends
    assert content.index("<h2>People</h2>") > legends
    assert "Kitchen" in content[legends:]
    assert "Alice" in content[legends:]
    assert "Bob (victim)" in content[legends:]
    assert len(document.with_class("has-clues")) == 1
    assert content.index('aria-labelledby="clues-heading"') < board_column


def test_puzzle_html_hides_solution_but_keeps_map_names_and_clues() -> None:
    name = '<script>alert("person")</script> & Alice'
    generated = sample_solution(person_name=name)
    rule = InCoordinateRule(person=name, axis=CoordinateAxis.ROW, value=0)
    rules = Rules(rules=(rule,))
    solution = ParsedHTML(format_solution_html(generated, rules=rules))
    content = format_solution_html(generated, rules=rules, show_solution=False)
    puzzle = ParsedHTML(content)

    assert len(puzzle.with_class("person")) == 2
    assert all("hidden" in person for person in puzzle.with_class("person"))
    assert all("hidden" not in person for person in solution.with_class("person"))
    assert puzzle.with_class("person-badge") == solution.with_class("person-badge")
    assert puzzle.with_class("cell") == solution.with_class("cell")
    assert puzzle.with_class("furniture") == solution.with_class("furniture")
    assert escape(name) in content
    assert "Bob (victim)" in content
    assert f"<li>{escape(rule.description)}</li>" in content
    coordinates = [
        attrs for tag, attrs in puzzle.tags if tag == "small" and "data-solution" in attrs
    ]
    assert len(coordinates) == 2
    assert all("hidden" in attrs for attrs in coordinates)
    assert puzzle.with_class("solution-toggle") == [
        {
            "type": "button", "class": "solution-toggle", "id": "solution-toggle",
            "aria-pressed": "false", "aria-controls": "generated-map people-legend",
        }
    ]
    assert solution.with_class("solution-toggle") == []
    assert sum(tag == "script" for tag, _ in puzzle.tags) == 1
    assert not any(
        attribute.startswith("on") for _, attrs in puzzle.tags for attribute in attrs
    )
    assert "<title>Murdoku - Generated puzzle</title>" in content
    assert not any(tag in ("link", "iframe") for tag, _ in puzzle.tags)
    assert not any("src" in attrs for _, attrs in puzzle.tags)
    assert name not in content
