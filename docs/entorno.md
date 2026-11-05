# Entorno de la estación

Código en `sim/mapa.py` y `sim/env.py`. Interfaz formal en [contratos.md](contratos.md).

## Formato de mapas

Los mapas son archivos de texto en `data/mapas/`, un carácter por casilla. Todas las filas deben tener el mismo ancho; las líneas vacías se ignoran.

| Símbolo | Significado | ¿Se camina? |
|---|---|---|
| `#` | pared | no |
| `.` | piso | sí |
| `+` | puerta | sí |
| `L` | casillero (escondite) | no |

Coordenadas `(x, y)`: `x` es la columna, `y` la fila, con `(0, 0)` en la esquina superior izquierda. Fuera del mapa cuenta como pared.

El mapa por defecto es `data/mapas/vela9.txt` (15 filas por 24 columnas, 8 casilleros, 8 salas).

## Salas

Las salas no se deducen del mapa: se anotan a mano en un archivo aparte. El motivo está en la decisión D6 de [decisiones.md](decisiones.md): la fila 5 de `vela9.txt` tiene aberturas sin puerta, así que separar por puertas da solo 6 zonas en vez de 8 salas.

### Formato del archivo de salas

- Nombre: `<mapa>_salas.txt` en la misma carpeta del mapa. `Mapa.desde_archivo` lo busca solo; también se puede pasar con `ruta_salas`. Si no existe, el mapa carga sin salas (`n_salas == 0`).
- Primera línea: `nombres: ` seguido de los nombres separados por comas. El orden define el índice de cada sala.
- Después, una cuadrícula del mismo tamaño que el mapa:
  - un dígito (índice de sala) en cada casilla de piso `.` o casillero `L`;
  - `#` exactamente donde el mapa tiene pared;
  - `+` exactamente donde el mapa tiene puerta.
- Como cada sala es un solo dígito, un mapa admite hasta 10 salas.

Reglas que `Mapa` valida al cargar (si alguna falla, lanza `ValueError` con la casilla del problema):

- El tamaño coincide con el del mapa.
- `#` y `+` están exactamente donde el mapa los tiene.
- Toda casilla de piso o casillero tiene un dígito.
- Todo dígito tiene nombre y todo nombre se usa.
- Cada sala está conectada por sus propias casillas de piso (un BFS que no sale de la sala ni pasa por puertas), y cada casillero toca una casilla de piso de su sala.

Las paredes y las puertas no pertenecen a ninguna sala: `sala(x, y)` devuelve `-1` en ellas y fuera del mapa. Los casilleros pertenecen a la sala en la que están.

### Salas de vela9

| Índice | Sala | Casillas |
|---|---|---|
| 0 | Médico | 24 |
| 1 | Laboratorio | 28 |
| 2 | Comunicaciones | 28 |
| 3 | Corredor A | 33 |
| 4 | Corredor B | 36 |
| 5 | Bodega | 20 |
| 6 | Reactor | 36 |
| 7 | Hangar | 24 |

`data/mapas/vela9_salas.txt`:

```
nombres: Médico, Laboratorio, Comunicaciones, Corredor A, Corredor B, Bodega, Reactor, Hangar
########################
#000000#1111111#2222222#
#000000#1111111#2222222#
#000000+1111111+2222222#
#000000#1111111#2222222#
###+####333#444####+####
#3333333333#44444444444#
#3333333333#44444444444#
#3333333333#44444444444#
###+#####+###+######+###
#55555#666666666#777777#
#55555#666666666#777777#
#55555+666666666+777777#
#55555#666666666#777777#
########################
```

Las aberturas de la fila 5 (columnas 8 a 10 y 12 a 14) se asignan a los corredores, no al Laboratorio.

### Ejemplo

```python
from sim import EstacionEnv, Mapa

m = Mapa.desde_archivo("data/mapas/vela9.txt")
print("salas:", m.n_salas)
for i, nombre in enumerate(m.nombres_salas):
    print(i, nombre, int((m.salas == i).sum()), "casillas")
print("(1, 1):", m.nombres_salas[m.sala(1, 1)])
print("(7, 3) puerta:", m.sala(7, 3))

env = EstacionEnv()
env.reset(semilla=42)
x, y = env.tripulante
print("tripulante en", (x, y), "sala:", env.mapa.nombres_salas[env.mapa.sala(x, y)])
```

Salida:

```
salas: 8
0 Médico 24 casillas
1 Laboratorio 28 casillas
2 Comunicaciones 28 casillas
3 Corredor A 33 casillas
4 Corredor B 36 casillas
5 Bodega 20 casillas
6 Reactor 36 casillas
7 Hangar 24 casillas
(1, 1): Médico
(7, 3) puerta: -1
tripulante en (2, 12) sala: Bodega
```

## Reglas

**Movimiento.** En cada tick el alienígena se mueve una casilla en una de las cuatro direcciones. Si la casilla de destino es pared o casillero, se queda donde está. No hay movimiento diagonal.

**Orden del tick.** Primero se mueve el alienígena, luego el tripulante.

**Captura.** Hay captura si la distancia Manhattan entre alienígena y tripulante es 1 o menos. Se revisa justo después de mover al alienígena y otra vez después de mover al tripulante, así que si el alienígena llega a su lado, el tripulante no alcanza a escapar.

**Inicio.** El alienígena aparece en una casilla transitable al azar y el tripulante en otra a por lo menos `distancia_inicial` casillas (10 por defecto).

**Fin.** El episodio termina con la captura o al llegar a `max_ticks` (300 por defecto).

## Bot provisional del tripulante

El tripulante usa un bot simple:

- Opciones: quedarse quieto o moverse a una casilla vecina transitable, sin entrar a la casilla del alienígena.
- Si el alienígena está a 6 casillas o menos, elige al azar entre las opciones que más lo alejan de él.
- Si no, camina al azar.

Todas las decisiones aleatorias usan `env.rng`, así que con la misma semilla y las mismas acciones la partida se repite igual.

## Visión

Código en `sim/percepcion.py` (T08). Decisión D7 en [decisiones.md](decisiones.md).

El alienígena ve una casilla si se cumple, en este orden:

1. Es su propia casilla: siempre se ve.
2. Está a más de `ALCANCE_VISION` casillas: no se ve.
3. Está a menos de `RADIO_CERCANO` casillas: se ve si hay línea de vista, mire hacia donde mire.
4. En otro caso: debe estar dentro del cono (el coseno entre la dirección del alienígena y la casilla es al menos `COS_MIN_VISION`) y debe haber línea de vista.

| Parámetro | Valor | Significado |
|---|---|---|
| `ALCANCE_VISION` | 7.5 casillas (15 m) | Distancia máxima de visión, en línea recta entre centros. |
| `COS_MIN_VISION` | 0.45 | Semiángulo de unos 63 grados: el cono abarca unos 127 grados. |
| `RADIO_CERCANO` | 1.5 casillas (3 m) | Por debajo se ve en cualquier dirección; incluye las 8 casillas vecinas. |

Una casilla mide 2 m.

**Qué tapa la vista.** Solo las paredes. Las puertas y los casilleros no tapan. La línea de vista recorre la recta con el algoritmo de Bresenham y revisa las casillas intermedias; el origen y el destino no tapan. Bresenham no es simétrico, así que siempre se calcula desde el alienígena hacia la casilla observada.

**Dirección.** `env.direccion_alien` es `(0, 1)` (hacia abajo) al empezar. Con las acciones 0 a 3 pasa a ser la dirección intentada, aunque choque con una pared: así el alienígena puede girar sin avanzar. Con la acción 4 no cambia.

**En el entorno.** `env.campo_vision` es una matriz booleana `(alto, ancho)` con las casillas que ve; se recalcula en `reset()` y en cada tick, después de mover al alienígena. Nunca marca paredes. `info["ve_tripulante"]` es `True` si la casilla del tripulante está en `campo_vision` al final del tick. Con eso, `Avance` ya registra los eventos "vio al tripulante" y "perdió de vista al tripulante" ([avance.md](avance.md)).

```python
from sim import EstacionEnv
from sim.percepcion import linea_de_vista, ve_casilla

env = EstacionEnv()
env.reset(semilla=42)
print("alien:", env.alien, "mira hacia:", env.direccion_alien, "tripulante:", env.tripulante)
print("casillas que ve:", int(env.campo_vision.sum()))
for accion in (1, 1, 2):
    _, _, _, info = env.step(accion)
    print("tick", info["tick"], "alien:", env.alien, "mira hacia:", env.direccion_alien,
          "ve:", int(env.campo_vision.sum()), "casillas, ve al tripulante:", info["ve_tripulante"])
print("línea de vista (2, 3) -> (10, 3):", linea_de_vista(env.mapa, (2, 3), (10, 3)))
print("línea de vista (2, 1) -> (10, 1):", linea_de_vista(env.mapa, (2, 1), (10, 1)))
print("¿(2, 3) mirando a la derecha ve (6, 3)?", ve_casilla(env.mapa, (2, 3), (1, 0), (6, 3)))
print("¿y mirando a la izquierda?", ve_casilla(env.mapa, (2, 3), (-1, 0), (6, 3)))
```

Salida:

```
alien: (1, 2) mira hacia: (0, 1) tripulante: (2, 12)
casillas que ve: 15
tick 1 alien: (1, 2) mira hacia: (1, 0) ve: 29 casillas, ve al tripulante: False
tick 2 alien: (1, 2) mira hacia: (1, 0) ve: 29 casillas, ve al tripulante: False
tick 3 alien: (1, 3) mira hacia: (0, 1) ve: 11 casillas, ve al tripulante: False
línea de vista (2, 3) -> (10, 3): True
línea de vista (2, 1) -> (10, 1): False
¿(2, 3) mirando a la derecha ve (6, 3)? True
¿y mirando a la izquierda? False
```

En los ticks 1 y 2 el alienígena intenta ir a la derecha, pero el casillero (2, 2) lo bloquea: no se mueve, aunque gira y su campo cambia. La recta de (2, 3) a (10, 3) cruza la puerta (7, 3), que no tapa; la de (2, 1) a (10, 1) choca con la pared (7, 1).

## Rutas con A*

Código en `sim/rutas.py` (T09). Decisión D11 en [decisiones.md](decisiones.md).

- Movimientos en 4 direcciones con costo 1 por paso, sobre piso y puertas (los vecinos de `Mapa.vecinos`). Los casilleros y las paredes no se pisan, ni siquiera como destino.
- Heurística: distancia Manhattan. Nunca sobreestima con estos movimientos, así que el camino siempre tiene el largo mínimo.
- Desempate: entre casillas con el mismo `f = g + h` se expande primero la de menor `h`; si siguen empatadas, la que entró antes a la frontera. Los vecinos se generan en el orden arriba, derecha, abajo, izquierda. Así la misma consulta siempre devuelve el mismo camino.
- `ruta(mapa, origen, destino)` devuelve la lista de casillas de origen a destino, ambos incluidos; `[origen]` si son la misma casilla; `None` si no hay camino. El número de pasos es `len(camino) - 1`.
- `ruta_a_sala(mapa, origen, sala)` devuelve el camino más corto hasta la casilla transitable más cercana de la sala (índice de 0 a `n_salas - 1`). Usa A* con varias metas y como heurística la menor distancia Manhattan a las casillas de la sala. Si el origen ya está en la sala, devuelve `[origen]`.
- Errores: `ValueError` con mensaje en español si el origen o el destino están fuera del mapa o no son transitables, si el mapa no tiene salas o si la sala no existe.

```python
from sim import EstacionEnv
from sim.rutas import ruta, ruta_a_sala

env = EstacionEnv()
env.reset(semilla=42)
camino = ruta(env.mapa, env.alien, env.tripulante)
print("de", env.alien, "a", env.tripulante, ":", len(camino) - 1, "pasos")
print("camino:", camino)
lab = env.mapa.nombres_salas.index("Laboratorio")
camino = ruta_a_sala(env.mapa, env.alien, lab)
print("al Laboratorio:", len(camino) - 1, "pasos, termina en", camino[-1])
print("ya dentro:", ruta_a_sala(env.mapa, (10, 2), lab))
```

Salida:

```
de (1, 2) a (2, 12) : 15 pasos
camino: [(1, 2), (1, 3), (2, 3), (2, 4), (3, 4), (3, 5), (3, 6), (2, 6), (2, 7), (2, 8), (3, 8), (3, 9), (3, 10), (2, 10), (2, 11), (2, 12)]
al Laboratorio: 8 pasos, termina en (8, 3)
ya dentro: [(10, 2)]
```

El camino rodea el casillero (2, 2) y cruza las puertas (3, 5) y (3, 9).

## Limitaciones de la versión 0

- La visión (T08), las rutas con A* (T09) y el avance con eventos (T10) ya existen; ver las secciones de arriba y [avance.md](avance.md).
- Sin pistas: no existe `dar_pista` (T11) ni la reacción del alienígena a ella (T19).
- Casilleros no utilizables: el tripulante no se esconde y la acción 4 siempre cuenta como casillero vacío. No está en el plan actual.

La observación de 4 capas y la recompensa se conservan del diseño inicial, pero el agente no las usa (D8). El ejemplo de abajo las muestra porque son parte de la interfaz del entorno.

## Uso

```python
from sim import EstacionEnv

env = EstacionEnv(max_ticks=50)
obs = env.reset(semilla=42)
print("observación:", obs.shape, obs.dtype)
print("alien:", env.alien, "tripulante:", env.tripulante)

total = 0.0
terminado = False
while not terminado:
    obs, recompensa, terminado, info = env.step(1)  # siempre a la derecha
    total += recompensa
print("fin:", info, "recompensa total:", total)
```

Salida:

```
observación: (4, 15, 24) float32
alien: (1, 2) tripulante: (2, 12)
fin: {'tick': 50, 'capturado': False, 'distancia_real': 13, 've_tripulante': False} recompensa total: -50.0
```

También se puede pasar otro mapa: `EstacionEnv(mapa="data/mapas/otro.txt")` o `EstacionEnv(mapa=Mapa([...]))`.

## Cómo extenderlo

- **Mapas nuevos:** agregar un `.txt` en `data/mapas/` con los símbolos de arriba. `Mapa` valida el formato al cargarlo.
- **Nuevas mecánicas (visión, avance con eventos):** se agregan dentro de `EstacionEnv` sin cambiar las firmas de `reset` y `step`. Si hace falta información nueva, va en `info` y se documenta en [contratos.md](contratos.md).
- **Comportamiento del tripulante:** se cambia en `_paso_tripulante`; debe usar `self.rng` para seguir siendo reproducible.
- Cada cambio de reglas lleva su prueba en `tests/`.
