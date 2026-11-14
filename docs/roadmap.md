# **Documentación: Generador Automático de Puzles Lógicos (Murdoku)**

# **1\. Contexto del Problema**

El objetivo de este proyecto es automatizar la generación de puzles lógicos (estilo *Murdoku* o *Cluedo*) garantizando matemáticamente que cada instancia generada tenga una **única solución**.

El problema consiste en ubicar a un conjunto de personajes y elementos en una cuadrícula (mapa) que contiene habitaciones. En lugar de buscar la solución a partir de unas pistas dadas, el sistema realiza el proceso inverso (Instance Generation): parte de una solución válida generada al azar y busca el subconjunto óptimo de reglas que obliguen al jugador a llegar exactamente a esa misma configuración sin ninguna ambigüedad. Todo el flujo se orquesta empleando técnicas de Programación con Restricciones e Investigación Operativa (Logic-Based Benders Decomposition) a través de Google OR-Tools y el solver CP-SAT.

# **2\. Fase 1: Generador de Soluciones (Solución Objetivo \$S^\*\$)**

Antes de buscar las pistas, se necesita una "foto fija" válida del tablero. Para ello se utiliza el modelo base en CP-SAT.

Las reglas de este modelo generador espacial incluyen:

* **Topología de Cuadrícula:** Variables booleanas para celdas, identificadores de habitaciones (cada habitación debe contar con un mínimo de 4 celdas conectadas), presencia de personas y objetos (2-4 elementos con frecuencias de aparición predefinidas).  
* **Distribución de Personas:** Restricciones de filas y columnas (no se pueden repetir personas en la misma fila ni en la misma columna). Además, una persona solo puede compartir celda con un objeto si dicho objeto es del tipo "ocupable".  
* **La Condición del Asesino:** Se añade una restricción específica sobre la variable que representa al asesino. Éste debe encontrarse en una habitación cuya suma total de personas alojadas sea exactamente dos (el asesino y una persona más).  
* **Estocasticidad:** Para evitar extraer siempre la misma configuración óptima, el CP-SAT se configura con `PORTFOLIO_SEARCH` y semillas aleatorias. Al resolver, se extraen los valores finales obteniendo la **Solución Objetivo (\$S^\*\$)**.

# **3\. Fase 2: Construcción del Pool de Reglas**

Con la solución \$S^\*\$ fijada, se procede a instanciar todas las pistas lógicas posibles.

* **Plantillas de Reglas:** Se definen iteradores para lógicas clásicas (ej. ubicación en habitación, adyacencia de celdas, o compartir fila/columna).  
* **Filtrado Estricto sobre \$S^\*\$:** Se evalúan las plantillas frente a las coordenadas de la solución objetivo. El sistema **solo guarda las reglas que son estrictamente verdaderas** en \$S^\*\$. Esto elimina la explosión combinatoria desde el inicio.  
* **Metadatos:** Cada regla válida creada se etiqueta con sus personajes *protagonistas* y se le asigna un nivel de *dificultad* basado en su coste cognitivo (ej. "X comparte habitación con Y" es más fácil que "X está en la misma fila que Y").

# **4\. Fase 3: Subset de Reglas, Unicidad y Nivel de Dificultad**

El corazón matemático del sistema es un bucle Maestro-Subproblema de Cutting Planes. El optimizador selecciona reglas para alcanzar una dificultad dada y el subproblema verifica si esas reglas garantizan solución única.

## **4.1. El Modelo Maestro (Goal Programming)**

Se plantea un modelo de optimización para escoger qué reglas (variables binarias \$x\_r\$) formarán parte del puzle final:

* **Cobertura de Personajes:** Todo personaje (salvo el asesino) debe ser protagonista de al menos una regla seleccionada, garantizando un balance narrativo.  
* **Función Objetivo Lexicográfica:** Se aplica programación por metas (Goal Programming) para acercar la suma de la dificultad de las reglas elegidas a un **Target de Dificultad**. Para evitar la "trampa de relleno" (donde el solver mete reglas inútiles solo para sumar puntos y llegar a la meta), se usa un peso lexicográfico: la prioridad 1 es minimizar el error absoluto respecto a la dificultad, y la prioridad 2 es minimizar el número total de reglas.

```py
# Minimización Lexicográfica en CP-SAT
error = abs(suma_dificultad - TARGET_DIFFICULTY)
master_model.Minimize(error * 100 + num_reglas_totales)
```

## **4.2. El Subproblema (Demostración de Unicidad mediante CP-SAT)**

Una vez el Modelo Maestro escoge un conjunto candidato de reglas, se crea un Subproblema con el motor CP-SAT base.

1. Se inyectan como restricciones estrictas únicamente las reglas seleccionadas por el Maestro.  
2. Se inyecta una **Cláusula de Exclusión** (*Nogood Cut*) utilizando `AddBoolOr` sobre las variables negadas de la solución \$S^\*\$. El objetivo es obligar al solver a buscar una solución **diferente** a la original.  
3. **Evaluación:**  
   * Si CP-SAT devuelve `INFEASIBLE`: Las reglas no admiten ninguna otra solución. Se ha garantizado matemáticamente la **Unicidad**. El proceso concluye.  
   * Si CP-SAT devuelve `FEASIBLE`: El puzle es ambiguo (existe al menos una solución alternativa \$S\_{alt}\$). Se identifican qué reglas del pool global no se cumplen en \$S\_{alt}\$ y se añade un **Corte de Benders** al Modelo Maestro: *"Debes elegir al menos una de estas reglas rotas para prohibir esta solución alternativa"*. El bucle vuelve a iterar hasta converger.

# **5\. Arquitectura de Implementación (Clean Architecture)**

El diseño del código sigue una estructura modular basada en Arquitectura Hexagonal, separando el dominio matemático de los casos de uso (apps). Esto permite que el modelo CP-SAT sea escalable, fácil de probar y delegable.

El repositorio se estructura en tres capas principales:

## **5.1. Capa `domain` (El núcleo puro)**

Contiene las entidades y la lógica de las restricciones, totalmente agnósticas a la fase de resolución.

* **Entidades:** Clases para `Map`, `Person`, `Element`, `Room`, `GridCell` (inicializables a partir de configuraciones como `map.json`, `personas.json`, `element.json`).  
* **Motor de Reglas (Patrón Estrategia):** Cada regla es un objeto que hereda de una clase base `BaseRule` e implementa:  
  * `description`: El texto de la pista para el jugador.  
  * `protagonists`: Lista de personajes implicados (para asegurar la cobertura en el Modelo Maestro).  
  * `difficulty`: Peso cognitivo de la regla (para la optimización lexicográfica).  
  * `evaluate(solution)`: Método que devuelve `True/False` verificando lógicamente si la regla se cumple en una solución dada \$S^\*\$.  
  * `apply_to_model(model, vars_dict)`: Método que inyecta las restricciones reales y matemáticas en el modelo CP-SAT.

## **5.2. Capa `apps` (Casos de uso / Orquestadores)**

Cada app tiene una responsabilidad única. Reciben entidades claras de la capa de dominio como input y devuelven outputs deterministas. No conocen detalles matemáticos internos de las reglas.

* **solution\_creator (Fase 1):** Recibe el mapa y los elementos, construye el modelo CP-SAT base introduciendo aleatoriedad (semillas) y genera la Solución Objetivo (\$S^\*\$).  
* **pool\_generator (Fase 2):** Recibe la solución \$S^\*\$ y el catálogo global de reglas. Ejecuta `evaluate(S*)` sobre cada una y devuelve el *pool* filtrado de reglas verdaderas.  
* **solution\_checker (Validador):** Recibe un mapa y un subconjunto de reglas. Ejecuta `apply_to_model` de las reglas proporcionadas, resuelve el modelo y devuelve un booleano indicando si la solución es única. Si hay ambigüedad, devuelve la solución alternativa (\$S\_{alt}\$).  
* **problem\_builder (Fase 3):** Orquesta el bucle Benders (Master-Subproblem). Ejecuta el Modelo Maestro (Goal Programming) para seleccionar el subconjunto de reglas y llama internamente al `solution_checker` para verificar la unicidad. Si el checker le devuelve una \$S\_{alt}\$, el builder añade el corte (cláusula de exclusión) y repite.

## **5.3. Capa `mains` (Puntos de entrada)**

Son los scripts ejecutables de orquestación final. Se encargan exclusivamente de la entrada/salida (leer JSONs), instanciar las entidades del dominio, inyectarlas en las apps y devolver la respuesta al usuario.

* `main_generate_new_puzzle.py`: Conecta secuencialmente las apps (`solution_creator` \$\\rightarrow\$ `pool_generator` \$\\rightarrow\$ `problem_builder`) para generar un puzle desde cero.  
* `main_verify_puzzle.py`: Llama directamente a la app `solution_checker` pasándole un puzle ya hecho, ideal para testear reglas manuales o depurar un escenario concreto.

