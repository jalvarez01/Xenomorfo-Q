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

Mientras llegan los bots con estilos (T11), el tripulante usa un bot simple:

- Opciones: quedarse quieto o moverse a una casilla vecina transitable, sin entrar a la casilla del alienígena.
- Si el alienígena está a 6 casillas o menos, elige al azar entre las opciones que más lo alejan de él.
- Si no, camina al azar.

Todas las decisiones aleatorias usan `env.rng`, así que con la misma semilla y las mismas acciones la partida se repite igual.

## Limitaciones de la versión 0

- Sin visión: el alienígena no tiene línea de vista (T07).
- Sin ruido: no hay propagación de sonido por BFS (T08).
- Casilleros no utilizables: el tripulante no se esconde y la acción 4 siempre cuenta como casillero vacío (T09).
- Creencia uniforme: la capa 1 reparte la probabilidad por igual entre todas las casillas libres (T21).
- Sin pistas: la capa 3 está en ceros (T19).

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
fin: {'tick': 50, 'capturado': False, 'distancia_real': 13} recompensa total: -50.0
```

También se puede pasar otro mapa: `EstacionEnv(mapa="data/mapas/otro.txt")` o `EstacionEnv(mapa=Mapa([...]))`.

## Cómo extenderlo

- **Mapas nuevos:** agregar un `.txt` en `data/mapas/` con los símbolos de arriba. `Mapa` valida el formato al cargarlo.
- **Nuevas mecánicas (visión, ruido, casilleros):** se agregan dentro de `EstacionEnv` sin cambiar las firmas de `reset` y `step`. Si hace falta información nueva, va en `info` o en una capa de la observación, y se documenta en [contratos.md](contratos.md).
- **Bots con estilos:** reemplazan a `_paso_tripulante`; deben usar `self.rng` para seguir siendo reproducibles.
- Cada cambio de reglas lleva su prueba en `tests/`.
