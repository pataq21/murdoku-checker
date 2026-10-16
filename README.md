# Murdoku Checker

Cada problema se guarda en una carpeta independiente dentro de `inputs/`:

```text
inputs/
└── example/
		└── map.json
```

En versiones posteriores, cada carpeta podra incorporar `people.json` y
`rules.json` para formar un murdoku completo.

## Formato del mapa

`map.json` contiene una lista de celdas. Las coordenadas son indices enteros no
negativos que empiezan en cero. Todas las caracteristicas son opcionales y su
valor predeterminado es `false`.

```json
{
	"cells": [
		{
			"latitude": 0,
			"longitude": 0,
			"has_carpet": true,
			"has_plant": false,
			"has_sofa": false,
			"has_chair": false
		}
	]
}
```

No puede haber dos celdas con las mismas coordenadas y no se admiten campos
desconocidos ni conversiones implicitas de tipos.

## Carga

```python
from murdoku_checker.loaders import load_map

map_ = load_map("inputs/example/map.json")
cell = map_.get_cell(0, 0)
```

El loader produce `FileNotFoundError` si el archivo no existe y
`pydantic.ValidationError` si el JSON o sus datos no son validos.

## Ejecucion

El flujo actual recibe la carpeta completa de un caso, carga su `map.json` y
crea el objeto `Map`:

```bash
uv run murdoku-checker inputs/example
```

Tambien puede ejecutarse mediante el script raiz:

```bash
uv run python main.py inputs/example
```

Por ahora el programa termina despues de validar y crear el mapa. Las personas,
las reglas logicas y la resolucion se incorporaran en fases posteriores.
