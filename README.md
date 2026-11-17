# Murdoku Checker

## Modelos matematicos en LaTeX

Cada caso de uso tiene un documento `.tex` independiente con los datos,
variables, restricciones, objetivo y criterios de resolucion implementados:

- [Generar una solucion](docs/modelos/generate-solution.tex): especificacion
  aleatoria, habitaciones conexas, muebles, personas y condicion de la victima.
- [Verificar un puzzle](docs/modelos/verify-puzzle.tex): colocacion sobre mapa
  fijo, formulacion de las familias de pistas y comprobacion de unicidad.
- [Generar un puzzle](docs/modelos/generate-puzzle.tex): fases de generacion,
  pool, maestro lexicografico, subproblema y cortes logicos de Benders.
- [Presentacion Beamer](docs/modelos/presentacion-generate-puzzle.tex): diapositivas
  en formato 16:9 sobre Murdoku, la arquitectura, el enfoque, la creacion del
  tablero y la construccion del problema, con ejemplos visuales y un anexo matematico.

Son documentos autonomos en espanol. Con una distribucion LaTeX instalada,
se pueden compilar desde la raiz del repositorio:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error -output-directory docs\modelos docs\modelos\generate-solution.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory docs\modelos docs\modelos\verify-puzzle.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory docs\modelos docs\modelos\generate-puzzle.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory docs\modelos docs\modelos\presentacion-generate-puzzle.tex
```

En la presentacion, ejecuta el comando dos veces para actualizar el total de
diapositivas y los enlaces internos.

La documentacion distingue las restricciones reales de cada fase: el checker
no reconstruye el mapa ni impone automaticamente la condicion de la victima
del generador, y la cobertura de pistas solo cuenta a su sujeto.

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
- `protagonists`: solo la persona sujeto de la pista (`person`).
- `evaluate(solution)`: si la regla se cumple en una `Solution`.
- `apply_to_model(model, variables)`: inyecta sus restricciones en el modelo
  CP-SAT. `to_literal(model, variables)` devuelve un booleano equivalente a la
  regla, usado para componerlas (por ejemplo en `any_of`).

Las clases concretas son `NextToRule`, `NotNextToRule`, `InRule`,
`InCoordinateRule`, `RelativePositionRule`, `RoomRelationRule` y `AnyOfRule`.
Todas incluyen su `person`; las reglas anidadas en `any_of` heredan la persona
de la disyuncion cuando se cargan desde JSON.

## Generacion del puzzle completo

El comando de generacion crea una solucion objetivo, genera el pool de pistas
verdaderas y selecciona un subconjunto optimo que garantiza solucion unica:

```powershell
uv run murdoku-generate use_cases\generate-puzzle\inputs\example.json
```

Tambien se puede ejecutar con
`uv run python -m murdoku_checker.mains.main_generate_new_puzzle use_cases\generate-puzzle\inputs\example.json`.
La salida JSON incluye `config`, `elements`, `solution` (mapa, posiciones,
victima y muebles), `pool`, `puzzle` y `optimization`.
`pool` es una lista de reglas con el formato de `rules.json`.
La lista agrupa las pistas por persona y no incluye pistas propias de la victima.
`puzzle` es un `MurdokuInput` completo (mapa, catalogo de elementos, personas y
solo las reglas seleccionadas). `optimization` indica `target_difficulty`,
`total_difficulty`, `difficulty_error`, `rule_count` e `iterations`.
Las personas sinteticas usan `gender: "Male"` como metadato; no interviene
en el modelo de colocacion.
`--solver-logs` envia los logs a stderr. Los errores se indican en stderr con
codigo 1 y sin salida JSON parcial.

La configuracion de `generate-puzzle` requiere `target_difficulty`, un entero
no negativo (por ejemplo, `"target_difficulty": 12`). `generate-solution`
no lo requiere. El maestro CP-SAT minimiza primero el error absoluto entre
la suma de dificultades y ese target; despues minimiza el numero de pistas.
El peso lexicografico es `len(pool) + 1`, no una constante que pueda dejar
de funcionar con pools grandes. Todos salvo `victim` deben ser el sujeto
(`person`) de alguna pista elegida. Cada regla tiene un unico protagonista:
la primera persona de la clausula; las personas referenciadas son `targets`
y no cuentan para cobertura. Esto tambien se aplica a `any_of`.
En esta fase se usa la victima como excepcion; no existe un asesino separado.

El checker excluye la colocacion objetivo completa y busca una alternativa.
Si existe, el maestro recibe un corte que exige alguna pista falsa en esa
alternativa. Solo se devuelve un resultado tras probar el optimo del maestro
y la ausencia de alternativas. Si el pool no permite cobertura o unicidad,
o un solver termina sin resultado concluyente, el comando informa del error:
no devuelve un puzzle ambiguo ni cambia la configuracion.

Los tres formatos ejecutan todas las fases. Texto y HTML muestran tambien las
pistas seleccionadas; HTML incluye una lista numerada a la izquierda del tablero, tanto
en el registro como en la copia opcional de `--output`. No muestra el pool
completo. Cada ejecucion de `generate-puzzle` guarda un unico `puzzle.html`.
Las posiciones de personas y sus coordenadas empiezan ocultas; el boton
`Show solution` las muestra y `Hide solution` las vuelve a ocultar.
Se conservan los nombres y la identificacion de la victima.
La solucion esta incluida en el archivo y puede consultarse en su codigo fuente:
es una ayuda visual, no una proteccion contra su lectura.
`--output` copia ese mismo HTML interactivo. No se crea otro `solution.html`.
El HTML incluye siempre como primera pista «Nombre is the victim. It was alone
with someone», usando el nombre de la victima, incluso sin pistas seleccionadas.
Esta pista informativa se cuenta en el HTML, pero no cambia las reglas ni las
metricas del puzzle.
El visor de `generate-solution` solo incluye esta pista y no crea `puzzle.html`.
El puzzle completo y sus metricas quedan siempre en `result.json`, junto a
los HTML, dentro del registro.

Cuando se genera el pool, stderr muestra `Generated rules per person:` con
el total de reglas de cada persona y un desglose por `rule.type`, antes del
resumen de tiempos. Cada regla `any_of` cuenta una sola vez; sus condiciones
internas no se cuentan como reglas adicionales. Las personas sin pistas
aparecen con `total=0`.

Durante `build_problem`, cada candidato comprobado produce una linea compacta
en stderr y `run.log`, sin necesidad de activar los logs de CP-SAT:

```text
Candidate 1 checked: difficulty=15 target=15 error=0 clues=5 status=ambiguous
Candidate 2 checked: difficulty=17 target=15 error=2 clues=6 status=unique
Puzzle summary: candidates_checked=2 cuts=1 unique_puzzles=1 difficulty=17 target=15 error=2 clues=6
```

`candidates_checked` cuenta subconjuntos de pistas comprobados en esta
ejecucion, no puzzles generados en ejecuciones anteriores ni soluciones
internas del solver. `error` es la distancia absoluta al target, no el gap de
optimalidad de CP-SAT. Un error cero no implica unicidad: `ambiguous` significa
que se encontro una alternativa. Solo se imprime el resumen final de exito
tras demostrar unicidad; los errores conservan los candidatos ya comprobados
y el diagnostico del fallo. Desde Python, `build_problem(on_progress=...)`
permite recibir los mismos datos como objetos `BuildProgress`; sin callback
la app no escribe estos mensajes.

El mismo JSON de entrada acepta `rule_types`, una lista opcional de tipos de
pistas que se generaran, por ejemplo `"rule_types": ["in", "in_coordinate", "any_of"]`.
Los valores admitidos son `in`, `next_to`, `not_next_to`, `in_coordinate`,
`room_relation`, `relative_position` y `any_of`. Si se omite, se habilitan todos;
una lista vacia desactiva todas las pistas (y normalmente impide formar un
puzzle con cobertura y unicidad). Los tipos desconocidos se rechazan
al cargar la configuracion. `any_of` solo combina reglas simples de los tipos
habilitados: seleccionarlo sin ningun tipo simple no produce pistas.
Esta opcion no modifica la generacion del tablero ni de la solucion.
La configuracion serializada incluye la lista efectiva de tipos, tambien cuando
se usan los valores por defecto.

## Registro de ejecuciones

Los tres comandos crean automaticamente una carpeta unica por ejecucion en
`use_cases/<caso-de-uso>/outputs/<fecha-UTC>_<id>/`, relativa al directorio
de trabajo. La ruta aparece en stderr como `Run directory:` sin alterar
el JSON o texto de stdout. `--runs-dir <carpeta>` cambia la carpeta padre.
Los ejemplos originales se guardan en `inputs/` dentro de cada caso de uso;
las carpetas `outputs/` por defecto se ignoran en Git.

Cada ejecucion conserva:

- `input.json`: copia exacta de la configuracion de generacion recibida.
- `config.json`: configuracion efectiva, incluidos valores por defecto y semilla.
  Si no se proporciono semilla, se elige una antes de generar la especificacion.
  Este archivo se puede usar directamente como entrada para repetir la ejecucion.
- En verificacion, `inputs/` sustituye a los dos archivos anteriores y conserva
  `map.json`, `elements.json`, `people.json`, `rules.json` e `image.png` si existe.
  Se resuelve la copia archivada, no los archivos originales.
- `result.json`: resultado estructurado, independiente del formato de consola.
  En generacion incluye tablero, muebles, posiciones y victima; en
  `generate-puzzle`, todos los formatos incluyen tambien el pool, el puzzle
  seleccionado y las metricas de optimizacion.
  En verificacion incluye el primer resultado y el recuento limitado a dos.
- `solution.html`: vista autocontenida de `generate-solution`. En verificacion es
  un informe con la cuadricula textual; tambien se guarda `solution.txt`.
- `puzzle.html`: unico HTML en `generate-puzzle`, con tablero, pistas y un boton
  para mostrar u ocultar la solucion integrada. Funciona sin conexion.
- `run.json`: argumentos, directorio de trabajo, rutas de origen, fechas,
  configuracion efectiva, version de Python y dependencias, revision Git y
  cambios locales, tiempos por fase, codigo de salida y estado.
- `run.log`: copia de stderr, incluidos los tiempos, los errores y los logs
  de CP-SAT si se uso `--solver-logs`.

No se reemplazan ejecuciones anteriores. Una ejecucion fallida conserva sus
entradas disponibles, metadatos y diagnosticos, aunque no tenga resultado.
Los errores al registrar una ejecucion son errores del comando (codigo 1),
no se ignoran. Los errores de uso de argumentos se detectan antes de crear
la carpeta. Las llamadas directas a las apps desde Python no crean registros.
Una revision Git con cambios locales se indica en los metadatos, pero no se
copia el codigo fuente: para reproducibilidad completa conviene usar un commit
limpio y las versiones registradas.

## Generacion de soluciones aleatorias (solution_creator)

La primera etapa de `solution_creator` genera una especificacion, todavia sin
coordenadas, habitaciones construidas ni solucion CP-SAT:

```python
from murdoku_checker.apps.solution_creator import generate_solution, generate_specification
from murdoku_checker.domain import GenerationConfig

config = GenerationConfig(
    rows=4,
    columns=4,
    element_coverage_percent=50,
    element_type_count=3,
    room_count=4,
    seed=17,
)
specification = generate_specification(config)
generated = generate_solution(specification)
if generated is None:
    print("No solution for the generated specification.")
else:
    solution = generated.solution
```

Los JSON de `generate-solution` y `generate-puzzle` aceptan nombres de personas
y un diccionario opcional `elements` con las propiedades de cada elemento:

```json
{
  "person_names": ["Alice", "Bob", "Carol", "David"],
  "elements": {
    "Table": {"size": 2, "is_occupiable": false},
    "Chair": {"size": 1, "is_occupiable": true},
    "Sofa": {"size": 2, "is_occupiable": true}
  }
}
```

Son campos adicionales de la configuracion: `person_names` debe tener exactamente
`min(rows, columns)` nombres unicos y no vacios (ni solo espacios).
`elements` sustituye a `element_names` y `element_sizes`; sus claves son nombres
no vacios y debe contener exactamente `element_type_count` entradas.
La ultima persona sigue siendo la victima. Si se omite `person_names`, se conservan
los nombres por defecto `person_1`, etc. Si se omite `elements`, se generan
`element_1`, etc., con tamaños y ocupabilidad aleatorios como antes.
Los nombres se usan en las pistas, el mapa y las salidas JSON, texto y HTML.
Cada valor de `elements` requiere `size`: un entero `1` o `2`, el numero de
celdas de cada ejemplar. Los tamaños configurados no se cambian al generar.
Las cantidades de ejemplares y sus posiciones siguen siendo generadas.
La cobertura debe permitir al menos un ejemplar de cada tipo y rellenarse
exactamente con esos tamaños; solo elementos de tamaño 2 requieren un total par.
`is_occupiable: true` permite colocar personas sobre ese elemento y `false`
lo bloquea; solo se aceptan booleanos JSON. En un objeto, si se omite
`is_occupiable`, su valor es `false`.

Para probarlo desde la consola con [la configuracion de ejemplo](use_cases/generate-solution/inputs/example.json):

```powershell
uv run murdoku-creator use_cases\generate-solution\inputs\example.json
```

Para visualizar la cuadricula con el visor compartido `solution_display`:

```powershell
uv run murdoku-creator use_cases\generate-solution\inputs\example.json --format text
```

El modo texto muestra personas, habitaciones, celdas bloqueadas y una leyenda.
Sin `--format` la salida sigue siendo JSON; tambien se puede indicar
`--format json`.

Para crear un mapa HTML visual y autocontenido:

```powershell
uv run murdoku-creator use_cases\generate-solution\inputs\example.json --format html
```

Abre `solution.html` dentro de la carpeta de la ejecucion indicada en stderr.
La vista de `generate-solution` funciona sin conexion, JavaScript ni dependencias
externas. El `puzzle.html` de `generate-puzzle` usa JavaScript integrado para
mostrar u ocultar la solucion, sin dependencias externas. F5 registra una
ejecucion de `generate-puzzle` y muestra el progreso compacto, sin los logs
detallados del solver.
Cada habitacion tiene un color y bordes marcados;
los muebles ocupables y bloqueados tienen estilos distintos. Cada ejemplar
muestra directamente su nombre, sin identificadores
`F1`, `F2`, etc. ni leyenda de objetos. Los muebles de dos celdas se dibujan
como una sola pieza horizontal o vertical. Las
personas se superponen a su celda. Las leyendas de personas y habitaciones
aparecen debajo del tablero. En pantallas pequeñas, las pistas aparecen antes
del tablero y la cuadricula se puede desplazar sin comprimir las celdas.
Los muebles cuyo nombre es exactamente `Chuso` o `Montse` muestran la imagen
incluida en `murdoku_checker/assets/chuso.png` o
`murdoku_checker/assets/montse.png`, respectivamente, conservando su nombre y
las personas superpuestas. Las imagenes se incrustan en el HTML y funcionan
sin archivos externos, tambien cuando la solucion del puzzle esta oculta.

`--output` es opcional: permite guardar una copia HTML adicional. En
`murdoku-creator` es exclusivo del modo HTML. La carpeta de destino
debe existir; un archivo de copia existente se reemplaza. No se permite usar
la propia configuracion como destino. Los errores de escritura se notifican
en stderr con codigo 1. JSON y texto mantienen su salida por consola.

El punto de entrada `main_generate_solution` prepara la especificacion y resuelve
su colocacion mediante CP-SAT. Tambien se puede ejecutar como modulo:

```powershell
uv run python -m murdoku_checker.mains.main_generate_solution use_cases\generate-solution\inputs\example.json
```

La colocacion prioriza amueblar el mayor numero posible de habitaciones, por
encima del criterio de proximidad a las semillas de las habitaciones. Es una
preferencia, no una restriccion obligatoria: si faltan muebles o alguna habitacion
no admite las piezas disponibles, se permiten habitaciones sin objetos.
Las personas no cuentan como muebles. Se mantienen los tamaños, cantidades,
ocupabilidad y restricciones geometricas de las piezas y habitaciones.
Si se alcanza el limite de tiempo, se conserva la mejor colocacion valida
encontrada, aunque no se haya demostrado que minimice las habitaciones vacias.

La salida es JSON con la configuracion, `person_count`, `element_cell_count`,
los tipos generados (`element`, `size`, `count`), `map`, `placements`, `victim`
y `furniture`.
`map.cells` contiene todas las celdas con su habitacion y sus features.
`placements` asigna a cada nombre `person_1`, `person_2`, etc. sus coordenadas
`[fila, columna]`. Cada entrada de `furniture` identifica un ejemplar mediante
su tipo (`element`) y sus coordenadas (`cells`), distinguiendo asi ejemplares
del mismo tipo aunque se toquen.
`victim` identifica a la ultima persona (`person_N`), que comparte habitacion
con exactamente otra persona. El visor de texto la marca con `*`; en HTML
tambien tiene un color distintivo y aparece identificada en la leyenda.

Se puede cambiar el JSON de entrada para probar otros parametros. Los errores
de lectura, validacion o resolucion se muestran en stderr con codigo de salida
1, sin JSON parcial; una generacion correcta devuelve 0. Si CP-SAT demuestra
que no existe colocacion, se informa de ello: no se cambian parametros,
tamaños ni ocupabilidad, ni se generan especificaciones nuevas automaticamente.
Un estado no concluyente del solver se informa como error, no como imposibilidad.

### Logs de CP-SAT

Ambos comandos admiten `--solver-logs` para mostrar las estadisticas iniciales
del modelo, presolve, progreso de busqueda y resumen final del solver:

```powershell
uv run murdoku-creator use_cases\generate-solution\inputs\example.json --format text --solver-logs
uv run murdoku-checker use_cases\verify-puzzle\inputs\so_easy\example1 --solver-logs
```

Los logs se envian a stderr para mantener stdout limpio en JSON, texto y HTML.
Estan desactivados por defecto, tambien en la configuracion de depuracion
de VS Code (F5); `--solver-logs` los habilita ademas del resumen compacto.
Desde Python se pueden activar con
`solver_logs=True` en `generate_solution`, `check_solutions` y los metodos
de resolucion de sus modelos.

### Tiempos por fase

Los tres puntos de entrada (`murdoku-checker`, `murdoku-creator` y
`murdoku-generate`) escriben siempre un resumen `Phase timings:` en stderr al
terminar, con segundos por fase y un total. Se miden la carga y validacion,
la generacion de la especificacion, `generate_solution`, `generate_pool` o
`check_solutions`, segun el comando, y la salida. Solo aparecen las fases
ejecutadas; si una falla, se incluye el tiempo transcurrido hasta el fallo.
En `murdoku-generate`, `build_problem` mide el bucle maestro-checker y
`log_pool_summary` mide el resumen de pistas en stderr;
`output` mide la salida del formato elegido, incluido JSON.
El total incluye tambien el procesamiento de argumentos. Los tiempos usan
un reloj monotono y no alteran stdout ni los archivos generados.

La configuracion tambien se puede leer con `GenerationConfig.model_validate_json`.
El numero de personas es `min(rows, columns)`. El presupuesto de celdas con
muebles es `round(rows * columns * element_coverage_percent / 100)`: se redondea
al entero mas cercano y, en empates, al par (4.5 da 4; 5.5 da 6). Puede dar cero.
El porcentaje mide celdas cubiertas, no el numero de ejemplares.

Todos los tipos deben aparecer. Se rechaza la configuracion si no hay al menos
una celda por tipo, si hay cobertura positiva sin tipos o si hay mas habitaciones
que celdas. Por ejemplo, 3x3 con 5% de cobertura y tres tipos es incompatible.
Las dimensiones y habitaciones son positivas; el porcentaje va de 0 a 100 y
el numero de tipos puede ser cero. No se aceptan campos adicionales ni
conversiones implicitas de tipos.

Cada entrada de `specification.elements` contiene un `element` del catalogo,
un `size` de 1 o 2 celdas y un `count` de ejemplares. Los nombres generados son
`element_1`, `element_2`, etc. La ocupabilidad y el tamaño se eligen por tipo:
todos los ejemplares de un tipo comparten ambas propiedades. Los tamaños se
eligen entre combinaciones compatibles con el presupuesto; despues se añaden
ejemplares hasta cubrirlo exactamente, sin solapamientos previstos. Esto evita
fallos aleatorios por falta de espacio o por un presupuesto impar con tipos
exclusivamente de tamaño dos.

La semilla permite repetir la especificacion en el mismo entorno sin modificar
el generador aleatorio global. Si se omite, se usa una nueva fuente de azar.
El catalogo existente `Element` no cambia: tamaño y cantidad pertenecen a la
especificacion de generacion.

La primera etapa solo garantiza la capacidad numerica. La segunda busca una
colocacion que respeta estas restricciones:

- Exactamente `room_count` habitaciones no vacias, conectadas por lados.
  Cada habitacion contiene una casilla semilla fijada antes de resolver:
  la primera se sortea y las siguientes maximizan la distancia Manhattan
  a la semilla mas cercana, con desempates aleatorios reproducibles.
  Se permiten rectangulos y formas en L. Cada fila o columna intersecta
  una habitacion en un unico tramo continuo: no se permiten huecos ni
  formas en U. El area ocupa al menos el 75% del rectangulo envolvente
  (`4 * area >= 3 * alto * ancho`) para limitar formas demasiado dispersas.
  La proporcion entre alto y ancho de la envolvente sigue limitada a 1.5.
- El solver minimiza la distancia a las semillas, con un pequeno coste
  aleatorio por casilla y habitacion para variar las fronteras. Esto favorece
  habitaciones locales sin exigir tamanos iguales. La busqueda dura como
  maximo 10 segundos; puede devolver una solucion valida sin demostrar
  optimalidad. Si no obtiene ninguna ni demuestra infactibilidad, informa
  de un error, no de que el mapa sea imposible.
- Como maximo una habitacion puede estar contenida en una sola fila o una
  sola columna, contando ambas orientaciones juntas. Puede no haber ninguna.
  Una habitacion de una celda cuenta una sola vez; las demas deben ocupar
  al menos dos filas y dos columnas. Con el limite de proporcion, la unica
  habitacion de una fila o columna permitida es una de 1x1. Puede no haber
  ninguna. Estas restricciones solo se aplican al generar mapas, no al
  verificar puzzles existentes. Pueden hacer infactibles configuraciones
  posibles con otra distribucion de semillas; el generador lo informa sin
  cambiar el numero de habitaciones. Otra semilla puede dar un mapa viable.
- Cada celda pertenece a una habitacion y admite como maximo un mueble.
- Cada ejemplar ocupa exactamente su tamaño; los de dos celdas son contiguos
  horizontal o verticalmente y estan dentro de la misma habitacion.
- Cada persona ocupa una celda, con como maximo una persona por fila y columna.
  Solo puede coincidir con muebles ocupables.
- La ultima persona es la victima. Su habitacion contiene exactamente dos
  personas en total; las demas habitaciones no tienen restricciones adicionales
  de cantidad de personas. Con menos de dos personas no hay solucion. Tampoco
  hay solucion con una sola habitacion y mas de dos personas.

El resultado reutiliza `Solution` y conserva la especificacion original y los
ejemplares colocados en `GeneratedSolution`. Las habitaciones reciben nombres
`room_1`, `room_2`, etc. El solver usa una sola hebra y busqueda aleatorizada con
semilla: la misma entrada y semilla son reproducibles en el mismo entorno.
No se garantiza muestreo uniforme ni que semillas diferentes siempre produzcan
tableros distintos.

Esta etapa genera una solucion objetivo, no un puzle con pistas ni una prueba
de unicidad. La seleccion de pistas y los demas atributos narrativos de las
personas (genero, gafas, etc.) quedan para etapas posteriores.

## Pool de pistas verdaderas (pool_generator)

La app `pool_generator` recibe una `Solution` objetivo y devuelve un diccionario
`dict[str, list[Rule]]`, agrupado por persona, con reglas verdaderas.
Las disyunciones `any_of` solo se incluyen si exactamente una de sus
condiciones es verdadera en la solucion objetivo; se excluyen las parejas
verdadera + verdadera y falsa + falsa. La regla sigue teniendo semantica OR,
no XOR, al evaluar otras soluciones.

```python
from murdoku_checker.apps.pool_generator import generate_pool
from murdoku_checker.domain import Rules

# generated es el resultado no nulo de generate_solution(specification).
pool = generate_pool(
    generated.solution, victim=generated.victim, rule_types=config.rule_types
)
for person, rules in pool.items():
    for rule in rules:
        print(person, rule.description, rule.difficulty, sorted(rule.protagonists))

rules_json = Rules(
    rules=tuple(rule for rules in pool.values() for rule in rules)
).model_dump_json(indent=2)
```

`iter_candidate_rules(solution)` permite recorrer los candidatos antes de
filtrar y acepta el mismo argumento opcional `rule_types` (una tupla en Python).
Si se omite, ambas funciones generan todos los tipos.
El universo se limita a las personas, habitaciones y features presentes
en el mapa objetivo y comprende:

- `in`: cada persona con cada habitacion o feature, con y sin `is_unique`.
- `next_to` y `not_next_to`: cada persona con cada feature.
- `in_coordinate`: cada persona con cada fila y columna existente.
- `room_relation`: pares ordenados de personas distintas, `same` y `different`.
- `relative_position`: las cuatro direcciones respecto a otra persona o a una
  persona anonima sobre/junto a una feature. Incluye distancia libre y todos los
  offsets positivos que pueden darse entre las coordenadas del mapa.
- `any_of`: todas las parejas no ordenadas de reglas simples distintas para la
  misma persona, sin anidamiento. Se forman antes del filtrado: una alternativa
  falsa y otra verdadera constituyen una disyuncion verdadera.

El orden es determinista, no se generan autorreferencias entre personas y los
nombres de features repetidos en varias celdas solo se enumeran una vez.
El comando pasa `victim=generated.victim`: no se construyen candidatas ni una
entrada de pool para la victima, cuyo texto propio es "es la victima".
La victima sigue disponible como referencia en pistas de otras personas.
Desde Python, `victim` es opcional porque una `Solution` no identifica a la
victima; si se omite, se generan pistas para todas las personas.
Una victima desconocida o una persona fuera del mapa provoca un error
explicito; una solucion sin personas produce un pool vacio.

El pool conserva las propiedades y la serializacion del catalogo existente.
Solo se comprueba veracidad, no utilidad, dificultad objetivo ni minimalidad:
puede contener redundancias y tautologias, que se trataran en la seleccion de
pistas. Con `k` reglas simples por persona se generan `k * (k - 1) / 2`
disyunciones; el coste crece cuadraticamente. El iterador no materializa todos
los candidatos juntos, pero `generate_pool` si conserva todas las pistas
aceptadas en el diccionario final. Con `v` reglas simples verdaderas y `f`
falsas para una persona, el pool contiene `v * f` disyunciones.

## Casos

Los ejemplos se agrupan por caso de uso. Los problemas de verificacion
se guardan por dificultad:

```text
use_cases/
  generate-puzzle/
    inputs/example.json
    outputs/<run-id>/
  generate-solution/
    inputs/example.json
    outputs/<run-id>/
  verify-puzzle/
    inputs/so_easy/
      example1/
      example2/
      example3/
      example4/
      example5/
    outputs/<run-id>/
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
  Las pistas muestran ese mismo indice, tambien dentro de disyunciones `any_of`,
  para coincidir con las etiquetas del tablero.
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

map_ = load_map(r"use_cases\verify-puzzle\inputs\so_easy\example1\map.json")
elements = load_elements(r"use_cases\verify-puzzle\inputs\so_easy\example1\elements.json")
people = load_people(r"use_cases\verify-puzzle\inputs\so_easy\example1\people.json")
rules = load_rules(r"use_cases\verify-puzzle\inputs\so_easy\example1\rules.json")
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

```powershell
uv run murdoku-checker use_cases\verify-puzzle\inputs\so_easy\example1
```

Tambien puede ejecutarse como modulo:

```powershell
uv run python -m murdoku_checker.mains.main_verify_puzzle use_cases\verify-puzzle\inputs\so_easy\example1
```

La salida comienza directamente con uno de estos resultados, sin mensajes de carga:

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
