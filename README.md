# Murdoku Checker

Cada problema se guarda en una carpeta independiente dentro de `inputs/`:

```text
inputs/
└── example/
		├── map.json
		├── people.json
		└── rules.json
```

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

Las caracteristicas admitidas son `bed`, `box`, `carpet`, `chair`, `counter`,
`plant`, `table`, `tree` y `wardrobe`. Un objeto que ocupa varias celdas se
incluye en las caracteristicas de cada una de ellas.

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

- `next_to` exige estar junto a una feature.
- `in` exige estar en una room o en una celda con una feature. `is_unique`
  indica si debe ser la unica persona en ese elemento y vale `false` por
  defecto.
- `any_of` expresa una disyuncion de al menos dos condiciones y puede contener
  otras condiciones `any_of`.

Los elementos son objetos tipados para diferenciar rooms de features.

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

Las personas, rooms y features referenciadas deben existir en los otros
archivos del caso.

## Carga

```python
from murdoku_checker.domain import MurdokuInput
from murdoku_checker.loaders import load_map, load_people, load_rules

map_ = load_map("inputs/example/map.json")
people = load_people("inputs/example/people.json")
rules = load_rules("inputs/example/rules.json")
input_ = MurdokuInput(map=map_, people=people, rules=rules)
cell = map_.get_cell(0, 0)
```

El loader produce `FileNotFoundError` si el archivo no existe y
`pydantic.ValidationError` si el JSON o sus datos no son validos.

## Ejecucion

El flujo actual recibe la carpeta completa de un caso, carga `map.json`,
`people.json` y `rules.json`, y valida el conjunto como un `MurdokuInput`:

```bash
uv run murdoku-checker inputs/example
```

Tambien puede ejecutarse mediante el script raiz:

```bash
uv run python main.py inputs/example
```

Por ahora el programa valida la estructura y las referencias de las reglas,
pero no intenta resolverlas. La colocacion de personas y la resolucion se
incorporaran en fases posteriores.
