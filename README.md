# Murdoku Checker

## Arquitectura

El codigo sigue la arquitectura por capas descrita en
[docs/roadmap.md](docs/roadmap.md):

```text
murdoku_checker/
??? domain/                  # Nucleo puro: entidades y motor de reglas
?   ??? grid_cell.py         # GridCell (celda de la cuadricula)
?   ??? room.py              # Room (habitacion y sus celdas)
?   ??? map.py               # Map (celdas, habitaciones y features)
?   ??? element.py           # Element (catalogo: elements.py)
?   ??? person.py            # Person (coleccion: people.py)
?   ??? solution.py          # Solution (colocacion de cada persona)
?   ??? murdoku_input.py     # Puzle completo con validacion de referencias
?   ??? rules/               # BaseRule y una clase por tipo de regla
??? apps/
?   ??? solution_checker/    # Modelo CP-SAT y comprobacion de unicidad
??? mains/                   # Entrada/salida: loaders, salida y CLI
    ??? main_verify_puzzle.py
```

Cada regla hereda de `BaseRule` (patron Estrategia) y expone:

- `description`: texto de la pista para el jugador (en ingles; filas y
  columnas se numeran desde 1).
- `difficulty`: coste cognitivo de la pista.
- `protagonists`: personas implicadas.
- `evaluate(solution)`: si la regla se cumple en una `Solution`.
- `apply_to_model(model, variables)`: inyecta sus restricciones en el modelo
  CP-SAT. `to_literal(model, variables)` devuelve un booleano equivalente a la
  regla, usado para componerlas (por ejemplo en `any_of`).

Las clases concretas son `NextToRule`, `NotNextToRule`, `InRule`,
`InCoordinateRule`, `RelativePositionRule`, `RoomRelationRule` y `AnyOfRule`.
Todas incluyen su `person`; las reglas anidadas en `any_of` heredan la persona
de la disyuncion cuando se cargan desde JSON.

## Casos

Cada problema se guarda por dificultad dentro de `inputs/`:

```text
inputs/
├── so_easy/
│   ├── example1/
│   ├── example2/
│   ├── example3/
│   ├── example4/
│   └── example5/
└── so_difficult/
    └── example6/
```

Cada carpeta de ejemplo contiene `elements.json`, `map.json`, `people.json`,
`rules.json` e `image.png`.

## Formato de los elementos

`elements.json` define el catalogo de elementos disponible para ese problema.
Cada elemento tiene un `name` unico y puede indicar si permite colocar una
persona en su celda mediante `is_occupiable`. Si se omite, su valor es `false`.

```json
{
	"elements": [
		{
			"name": "rock"
		},
		{
			"name": "carpet",
			"is_occupiable": true
		}
	]
}
```

Los nombres son especificos de cada problema: no existe un catalogo global y
se pueden añadir elementos nuevos sin modificar el codigo. No se admiten
nombres vacios, duplicados, campos desconocidos ni conversiones implicitas de
tipos.

## Formato del mapa

`map.json` contiene una lista de celdas. Las coordenadas son indices enteros no
negativos que empiezan en cero. `latitude` representa la fila de arriba abajo y
`longitude` la columna de izquierda a derecha. Cada celda debe indicar su
`room`; `features` es opcional y su valor predeterminado es una lista vacia.

```json
{
	"cells": [
		{
			"latitude": 0,
			"longitude": 1,
			"room": "comedor",
			"features": ["chair"]
		}
	]
}
```

Cada nombre incluido en `features` debe existir en el `elements.json` del
problema. Un objeto que ocupa varias celdas se incluye en las caracteristicas
de cada una de ellas. Una celda es ocupable solo si todos sus elementos tienen
`is_occupiable: true`.

No puede haber dos celdas con las mismas coordenadas y no se admiten campos
desconocidos, caracteristicas duplicadas ni conversiones implicitas de tipos.

## Formato de las personas

`people.json` contiene la lista de personas. El nombre y el genero son
obligatorios. `gender` admite `Male` o `Female`; `wear_glasses`, `is_bald` e
`is_victim` son opcionales y su valor predeterminado es `false`.

```json
{
	"people": [
		{
			"name": "Alice",
			"gender": "Female",
			"wear_glasses": false,
			"is_bald": false,
			"is_victim": false
		}
	]
}
```

No puede haber dos personas con el mismo nombre.

## Formato de las reglas

`rules.json` contiene restricciones asociadas a una persona. Cada regla tiene
una unica `condition`, discriminada por `type`:

- `next_to` exige estar junto a una feature: distancia Manhattan 1 (sin
  diagonales) y en la misma habitacion que el objeto.
- `not_next_to` es su contrario exacto: excluye las celdas que cumplen
  `next_to` para esa feature. Una celda diagonal o en otra habitacion no se
  considera adyacente. Si hay varios objetos con esa feature, no puede estar
  junto a ninguno de ellos en su misma habitacion.
- `in` exige estar en una room o en una celda con una feature. `is_unique`
  indica si debe ser la unica persona en ese elemento y vale `false` por
  defecto.
- `relative_position` compara la posicion con otra persona, indicada mediante
  un elemento `person`. `direction` admite `north` (menor latitude), `south`
  (mayor latitude), `west` (menor longitude) y `east` (mayor longitude).
  No exige adyacencia, compartir habitacion ni coincidir en el otro eje. El
  campo opcional `offset` exige una distancia exacta positiva en ese eje; si
  se omite, solo se exige estar en la direccion indicada. Cuando el elemento
  es una feature, la posicion se compara con una persona anonima que cumple
  `feature_relation`: `in` por defecto o `next_to`.
- `room_relation` compara la habitacion con otra persona. `relation` admite
  `same` y `different`.
- `in_coordinate` exige estar en una fila (`row`) o columna (`column`)
  concreta. `value` es el indice de la coordenada, empezando en cero.
- `any_of` expresa una disyuncion de al menos dos condiciones y puede contener
  otras condiciones `any_of`.

Los elementos son objetos tipados para diferenciar rooms, features y personas.
Solo `relative_position` admite un elemento de tipo `person`, cuya referencia
debe existir. Por ejemplo:

```json
{
    "person": "Brigitte",
    "condition": {
        "type": "relative_position",
        "direction": "south",
        "element": {"type": "person", "value": "Cameron"}
    }
}
```

Las comparaciones son estrictas: una persona nunca esta al norte, sur, este
u oeste de si misma. `relative_position` puede combinarse con las otras
condiciones en `any_of`, tambien anidados. Varias reglas de una persona
deben cumplirse simultaneamente.

Por ejemplo, estar exactamente una fila al sur de Donovan y en otra zona se
expresa mediante dos reglas:

```json
{
    "person": "Brandon",
    "condition": {
        "type": "relative_position",
        "direction": "south",
        "element": {"type": "person", "value": "Donovan"},
        "offset": 1
    }
},
{
    "person": "Brandon",
    "condition": {
        "type": "room_relation",
        "relation": "different",
        "element": {"type": "person", "value": "Donovan"}
    }
}
```

Por ejemplo, la ultima columna de un mapa de cinco columnas se expresa asi:

```json
{
    "person": "Corinne",
    "condition": {
        "type": "in_coordinate",
        "axis": "column",
        "value": 4
    }
}
```

`next_to` y `not_next_to` solo admiten elementos de tipo `feature`. Por ejemplo:

```json
{
    "person": "Ada",
    "condition": {
        "type": "not_next_to",
        "element": {"type": "feature", "value": "plant"}
    }
}
```

`not_next_to` tambien puede aparecer en `any_of`, incluso anidados o combinados
con condiciones `in` con `is_unique`. No hace ocupables las celdas bloqueadas:
el filtro de ocupacion se aplica igualmente. Como es la negacion de la
adyacencia, no prohibe por si sola estar sobre una feature ocupable.

```json
{
	"rules": [
		{
			"person": "Evangeline",
			"condition": {
				"type": "any_of",
				"conditions": [
					{
						"type": "next_to",
						"element": {"type": "feature", "value": "tree"}
					},
					{
						"type": "next_to",
						"element": {"type": "feature", "value": "plant"}
					}
				]
			}
		}
	]
}
```

Las personas, rooms y elementos referenciados deben existir en los otros
archivos del caso. Tambien deben estar declarados todos los elementos usados
por las celdas del mapa.

## Carga

```python
from murdoku_checker.domain import MurdokuInput
from murdoku_checker.mains.loaders import (
    load_elements,
    load_map,
    load_people,
    load_rules,
)

map_ = load_map("inputs/so_easy/example1/map.json")
elements = load_elements("inputs/so_easy/example1/elements.json")
people = load_people("inputs/so_easy/example1/people.json")
rules = load_rules("inputs/so_easy/example1/rules.json")
input_ = MurdokuInput(
    map=map_,
    elements=elements,
    people=people,
    rules=rules,
)
cell = map_.get_cell(0, 0)
```

El loader produce `FileNotFoundError` si el archivo no existe y
`pydantic.ValidationError` si el JSON o sus datos no son validos.

## Ejecucion

El programa recibe la carpeta completa de un caso, carga `map.json`,
`people.json` y `rules.json`, valida el conjunto y busca una solucion:

```bash
uv run murdoku-checker inputs/so_easy/example1
```

Tambien puede ejecutarse como modulo:

```bash
uv run python -m murdoku_checker.mains.main_verify_puzzle inputs/so_easy/example1
```

La salida incluye el resumen de carga y uno de estos resultados:

- `No solution.`: el caso no tiene solucion; no se imprime una cuadricula.
- `Unique solution.`: hay exactamente una solucion.
- `Multiple solutions (at least 2). Showing the first.`: hay varias soluciones.
  La busqueda se detiene al encontrar la segunda y solo muestra la primera;
  no calcula el total exacto.

La solucion se muestra como una cuadricula con coordenadas y leyenda:

```text
Unique solution.
First solution (rows = latitude, columns = longitude):
      0       1
0 | P1/R1 | #/R1  |
1 | ./R2  |       |

Legend:
  . = unoccupied cell; # = blocked cell; blank = no cell
  P1 = Alice (latitude=0, longitude=0)
  R1 = cocina
  R2 = comedor
```

Cada celda muestra `ocupante/habitacion`. Los identificadores `P1`, `P2`, etc.
siguen el orden de las personas del archivo; la leyenda conserva sus nombres
completos y posiciones. Las habitaciones se numeran por orden alfabetico.
`.` indica una celda sin persona, `#` una celda no ocupable y un hueco indica
que esa celda no existe. Solo se muestran las filas y columnas presentes en
el mapa, con sus coordenadas originales, incluso si no son consecutivas.

Un mapa vacio sin personas tiene una solucion vacia y se muestra como
`First solution: empty map.`. Los errores de carga o resolucion se escriben
en stderr y devuelven codigo 1; un caso valido sin solucion devuelve codigo 0.

Desde Python, `check_solutions(input_)` de
`murdoku_checker.apps.solution_checker` busca hasta 2 soluciones y devuelve
un `SolveResult`. `OptimizationModel.solve()` devuelve el numero de
soluciones encontradas (hasta 2 por defecto). `solve_with_solution()` devuelve
un `SolveResult` con `count` y `first_solution`: un mapping inmutable de nombre
a `(latitude, longitude)`, o `None` si no hay solucion. Ambos metodos aceptan
`max_solutions=None` para contar todas, aunque solo se conserva la primera
colocacion. Un limite de 1 no permite comprobar la unicidad.
